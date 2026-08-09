from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.models.gguf import read_gguf_metadata

_SHARD = re.compile(r"^(?P<base>.+)-(?P<part>\d{5})-of-(?P<total>\d{5})\.gguf$", re.IGNORECASE)


@dataclass(frozen=True)
class LocalModel:
    owner_principal_id: str
    root_path: str
    model_id: str
    name: str
    architecture: str
    quantization: str | None
    primary_path: str
    shard_count: int
    expected_shards: int
    complete: bool
    size_bytes: int
    indexed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelLibraryService:
    def __init__(self, store: Any) -> None:
        self.store = store

    def add_root(self, owner_principal_id: str, path: Path) -> str:
        if not path.is_absolute() or not path.exists() or not path.is_dir():
            raise ValueError("invalid_model_library_root")
        root = str(path.resolve())
        self.store.save_model_library_root(owner_principal_id, root)
        return root

    def remove_root(self, owner_principal_id: str, path: Path) -> bool:
        return self.store.delete_model_library_root(owner_principal_id, str(path.resolve()))

    def roots(self, owner_principal_id: str) -> list[str]:
        return self.store.list_model_library_roots(owner_principal_id)

    def list_models(self, owner_principal_id: str) -> list[LocalModel]:
        return self.store.list_local_models(owner_principal_id)

    def rescan(self, owner_principal_id: str) -> list[LocalModel]:
        models: list[LocalModel] = []
        for root_text in self.roots(owner_principal_id):
            root = Path(root_text).resolve()
            files: list[Path] = []
            for directory, dirs, names in os.walk(root, followlinks=False):
                dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
                for name in names:
                    candidate = Path(directory) / name
                    if candidate.suffix.lower() != ".gguf" or candidate.is_symlink():
                        continue
                    try:
                        candidate.resolve().relative_to(root)
                    except ValueError:
                        continue
                    files.append(candidate)
            models.extend(self._index_root(owner_principal_id, root, files))
        self.store.replace_local_models(owner_principal_id, models)
        return sorted(models, key=lambda model: model.name.casefold())

    @staticmethod
    def _index_root(owner: str, root: Path, files: list[Path]) -> list[LocalModel]:
        groups: dict[str, list[tuple[Path, int, int]]] = {}
        for path in files:
            match = _SHARD.match(path.name)
            key = match.group("base") if match else str(path.relative_to(root))
            groups.setdefault(key, []).append(
                (
                    path,
                    int(match.group("part")) if match else 1,
                    int(match.group("total")) if match else 1,
                )
            )
        result: list[LocalModel] = []
        for _key, shards in groups.items():
            shards.sort(key=lambda item: item[1])
            expected = shards[0][2]
            try:
                metadata = read_gguf_metadata(shards[0][0])
            except (OSError, ValueError):
                continue
            paths = [item[0] for item in shards]
            model_id = (
                "mdl_"
                + hashlib.sha256(str(paths[0].resolve()).casefold().encode("utf-8")).hexdigest()[
                    :24
                ]
            )
            result.append(
                LocalModel(
                    owner_principal_id=owner,
                    root_path=str(root),
                    model_id=model_id,
                    name=metadata.name,
                    architecture=metadata.architecture,
                    quantization=metadata.quantization,
                    primary_path=str(paths[0].resolve()),
                    shard_count=len(paths),
                    expected_shards=expected,
                    complete=len(paths) == expected
                    and {item[1] for item in shards} == set(range(1, expected + 1)),
                    size_bytes=sum(path.stat().st_size for path in paths),
                    indexed_at=utc_now(),
                )
            )
        return result
