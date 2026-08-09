from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

_FULL_REVISION = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
_SHARD = re.compile(r"^(?P<base>.+)-(?P<part>\d{5})-of-(?P<total>\d{5})\.gguf$", re.IGNORECASE)
_SAFETENSOR_SHARD = re.compile(
    r"^(?P<base>.+)-(?P<part>\d{5})-of-(?P<total>\d{5})\.safetensors$", re.IGNORECASE
)
_QUANTIZATION = re.compile(
    r"(?:^|[-_.])(IQ\d(?:_[A-Z0-9]+)*|Q\d(?:_[A-Z0-9]+)*)(?:[-_.]|$)", re.IGNORECASE
)


class HubClient(Protocol):
    def search(self, query: str, *, limit: int, token: str | None) -> Any: ...
    def model_info(self, repo_id: str, *, revision: str | None, token: str | None) -> Any: ...
    def snapshot_download(self, **kwargs: Any) -> Any: ...


class OfficialHubClient:
    def __init__(self) -> None:
        from huggingface_hub import HfApi, snapshot_download

        self._api = HfApi()
        self._snapshot_download = snapshot_download

    def search(self, query: str, *, limit: int, token: str | None) -> Any:
        return self._api.list_models(
            search=query, limit=limit, sort="downloads", token=token or False
        )

    def model_info(self, repo_id: str, *, revision: str | None, token: str | None) -> Any:
        from huggingface_hub.errors import GatedRepoError, RepositoryNotFoundError

        try:
            return self._api.model_info(
                repo_id, revision=revision, files_metadata=True, token=token or False
            )
        except (GatedRepoError, RepositoryNotFoundError) as exc:
            raise HubGatedError from exc

    def snapshot_download(self, **kwargs: Any) -> Any:
        return self._snapshot_download(**kwargs)


class HubGatedError(RuntimeError):
    pass


class HuggingFaceAccessError(RuntimeError):
    def __init__(self, code: str, repo_id: str) -> None:
        self.code = code
        self.repository_url = f"https://huggingface.co/{repo_id}"
        super().__init__(code)

    def __repr__(self) -> str:
        return f"HuggingFaceAccessError(code={self.code!r}, repository_url={self.repository_url!r})"


@dataclass(frozen=True)
class HfSearchResult:
    repo_id: str
    downloads: int
    likes: int
    gated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HfVariant:
    repo_id: str
    revision: str
    files: tuple[str, ...]
    format: str
    quantization: str | None
    total_bytes: int
    cached_bytes: int
    gated: bool
    license_id: str | None
    complete: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HfDownloadPreview:
    repo_id: str
    revision: str
    files: tuple[str, ...]
    total_bytes: int
    cached_bytes: int
    download_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HuggingFaceService:
    def __init__(self, hub: HubClient | None = None, *, cache_dir: Path) -> None:
        self.hub = hub or OfficialHubClient()
        self.cache_dir = cache_dir.resolve()

    def search(
        self, query: str, *, token: str | None = None, limit: int = 20
    ) -> list[HfSearchResult]:
        query = query.strip()
        if not query:
            raise ValueError("hugging_face_query_required")
        bounded = max(1, min(limit, 50))
        try:
            rows = self.hub.search(query, limit=bounded, token=token)
            return [
                HfSearchResult(
                    repo_id=str(row.id),
                    downloads=int(getattr(row, "downloads", 0) or 0),
                    likes=int(getattr(row, "likes", 0) or 0),
                    gated=bool(getattr(row, "gated", False)),
                )
                for row in rows
            ]
        except Exception as exc:
            raise HuggingFaceAccessError("hugging_face_unavailable", "models") from exc

    def repository(
        self, repo_id: str, *, revision: str | None = None, token: str | None = None
    ) -> Any:
        clean_repo = _validate_repo_id(repo_id)
        try:
            info = self.hub.model_info(clean_repo, revision=revision, token=token)
        except HubGatedError as exc:
            raise HuggingFaceAccessError("gated_access_required", clean_repo) from exc
        except Exception as exc:
            raise HuggingFaceAccessError("hugging_face_unavailable", clean_repo) from exc
        sha = str(getattr(info, "sha", "") or "")
        if not _FULL_REVISION.fullmatch(sha):
            raise ValueError("hugging_face_revision_not_immutable")
        return info

    def variants(
        self, repo_id: str, *, revision: str | None = None, token: str | None = None
    ) -> list[HfVariant]:
        info = self.repository(repo_id, revision=revision, token=token)
        sha = str(info.sha).lower()
        gated = bool(getattr(info, "gated", False))
        license_id = _license_id(getattr(info, "card_data", None))
        files = [
            (str(item.rfilename), _file_size(item))
            for item in (getattr(info, "siblings", None) or [])
        ]
        groups: dict[str, list[tuple[str, int, int, int]]] = {}
        singles: list[tuple[str, int]] = []
        for filename, size in files:
            if not filename.lower().endswith(".gguf"):
                continue
            match = _SHARD.match(filename)
            if match:
                groups.setdefault(match.group("base"), []).append(
                    (filename, int(match.group("part")), int(match.group("total")), size)
                )
            else:
                singles.append((filename, size))
        variants = [
            HfVariant(
                str(info.id),
                sha,
                (name,),
                "gguf",
                _quantization(name),
                size,
                0,
                gated,
                license_id,
                True,
            )
            for name, size in singles
        ]
        for _base, shards in groups.items():
            shards.sort(key=lambda row: row[1])
            expected = shards[0][2]
            complete = len(shards) == expected and {row[1] for row in shards} == set(
                range(1, expected + 1)
            )
            variants.append(
                HfVariant(
                    str(info.id),
                    sha,
                    tuple(row[0] for row in shards),
                    "gguf",
                    _quantization(shards[0][0]),
                    sum(row[3] for row in shards),
                    0,
                    gated,
                    license_id,
                    complete,
                )
            )
        safetensor_files = [
            (name, size) for name, size in files if name.lower().endswith(".safetensors")
        ]
        if safetensor_files:
            supporting = [(name, size) for name, size in files if _is_conversion_support_file(name)]
            selected = sorted(safetensor_files + supporting, key=lambda item: item[0])
            variants.append(
                HfVariant(
                    str(info.id),
                    sha,
                    tuple(name for name, _size in selected),
                    "safetensors",
                    None,
                    sum(size for _name, size in selected),
                    0,
                    gated,
                    license_id,
                    _safetensor_files_complete([name for name, _size in safetensor_files])
                    and any(name == "config.json" for name, _size in supporting),
                )
            )
        return sorted(
            variants,
            key=lambda item: (
                not item.complete,
                item.format != "gguf",
                _quant_rank(item.quantization),
                item.total_bytes,
            ),
        )

    def dry_run(
        self, repo_id: str, variant: HfVariant, *, token: str | None = None
    ) -> HfDownloadPreview:
        _validate_selection(repo_id, variant)
        rows = self.hub.snapshot_download(
            repo_id=repo_id,
            revision=variant.revision,
            allow_patterns=list(variant.files),
            token=token or False,
            cache_dir=self.cache_dir,
            dry_run=True,
        )
        total = sum(int(getattr(row, "file_size", 0) or 0) for row in rows)
        cached = sum(
            int(getattr(row, "file_size", 0) or 0)
            for row in rows
            if bool(getattr(row, "is_cached", False))
        )
        return HfDownloadPreview(
            repo_id, variant.revision, variant.files, total, cached, total - cached
        )

    def download(
        self, repo_id: str, variant: HfVariant, destination: Path, *, token: str | None = None
    ) -> Path:
        _validate_selection(repo_id, variant)
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        self.hub.snapshot_download(
            repo_id=repo_id,
            revision=variant.revision,
            allow_patterns=list(variant.files),
            token=token or False,
            cache_dir=self.cache_dir,
            local_dir=destination,
            dry_run=False,
        )
        return destination


def _validate_repo_id(repo_id: str) -> str:
    clean = repo_id.strip()
    if clean.count("/") != 1 or any(part in {"", ".", ".."} for part in clean.split("/")):
        raise ValueError("invalid_hugging_face_repository")
    return clean


def _validate_selection(repo_id: str, variant: HfVariant) -> None:
    if variant.repo_id != repo_id or not variant.complete:
        raise ValueError("incomplete_hugging_face_variant")
    if not _FULL_REVISION.fullmatch(variant.revision) or not variant.files:
        raise ValueError("hugging_face_revision_not_immutable")


def _file_size(item: Any) -> int:
    size = getattr(item, "size", None)
    if size is None and getattr(item, "lfs", None) is not None:
        size = getattr(item.lfs, "size", None)
    return max(0, int(size or 0))


def _license_id(card_data: Any) -> str | None:
    value = (
        card_data.get("license")
        if isinstance(card_data, dict)
        else getattr(card_data, "license", None)
    )
    return str(value) if value else None


def _quantization(filename: str) -> str | None:
    match = _QUANTIZATION.search(Path(filename).name.upper())
    return match.group(1).upper() if match else None


def _quant_rank(value: str | None) -> int:
    preferred = {"Q4_K_M": 0, "Q5_K_M": 1, "Q8_0": 2}
    return preferred.get(value or "", 10)


def _is_conversion_support_file(filename: str) -> bool:
    name = Path(filename).name.lower()
    exact = {
        "config.json",
        "generation_config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "added_tokens.json",
        "merges.txt",
        "vocab.json",
        "vocab.txt",
        "model.safetensors.index.json",
    }
    return name in exact or name.endswith(".model")


def _safetensor_files_complete(filenames: list[str]) -> bool:
    matches = [_SAFETENSOR_SHARD.match(name) for name in filenames]
    shard_matches = [match for match in matches if match is not None]
    if not shard_matches:
        return len(filenames) == 1
    if len(shard_matches) != len(filenames):
        return False
    expected = int(shard_matches[0].group("total"))
    return len(shard_matches) == expected and {
        int(match.group("part")) for match in shard_matches
    } == set(range(1, expected + 1))
