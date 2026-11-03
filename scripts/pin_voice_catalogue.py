# SPDX-License-Identifier: Apache-2.0
"""Pin the voice catalogue's Hugging Face items to a revision and a SHA-256.

Voice spec §5.6: nothing outside ``raiker/config/voice-catalogue.json`` is
downloaded, and nothing in it is installable without a digest. Whisper models
and Piper voices live on Hugging Face, which was unreachable where the
catalogue was first built, so those entries carry ``pending_reason``.

This script resolves each pending Hugging Face item without downloading it:
the repository's current commit (``/api/models/<repo>/revision/main``) becomes
the pinned revision, and the file's Git LFS object id — which *is* its SHA-256
— and size come from ``/api/models/<repo>/paths-info/<revision>``. The entry's
``url`` is then the immutable ``resolve/<revision>/<path>`` address, and its
``pending_reason`` is removed.

An item whose licence is not on the permissive list (a Piper voice whose
dataset licence has not been reviewed) gets its digest but stays pending until
``--licence-reviewed <id>`` names it, with the licence it was reviewed as.

    python -m scripts.pin_voice_catalogue                 # print what would change
    python -m scripts.pin_voice_catalogue --write         # update the catalogue
    python -m scripts.pin_voice_catalogue --write --licence-reviewed piper-voice-en_US-amy-medium=CC-BY-4.0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

CATALOGUE = Path(__file__).resolve().parents[1] / "raiker" / "config" / "voice-catalogue.json"
HF = "https://huggingface.co"


def _revision(client: httpx.Client, repo: str) -> str:
    answer = client.get(f"{HF}/api/models/{repo}/revision/main")
    answer.raise_for_status()
    sha = answer.json().get("sha")
    if not isinstance(sha, str) or len(sha) != 40:
        raise SystemExit(f"{repo}: no commit sha in the revision answer")
    return sha


def _file_info(client: httpx.Client, repo: str, revision: str, path: str) -> tuple[str, int]:
    answer = client.post(f"{HF}/api/models/{repo}/paths-info/{revision}", data={"paths": path, "expand": "true"})
    answer.raise_for_status()
    for entry in answer.json():
        if entry.get("path") == path:
            lfs = entry.get("lfs") or {}
            oid, size = lfs.get("oid") or lfs.get("sha256"), lfs.get("size") or entry.get("size")
            if isinstance(oid, str) and len(oid) == 64 and isinstance(size, int) and size > 0:
                return oid, size
    raise SystemExit(f"{repo}/{path}: no LFS digest at {revision}")


def pin(data: dict[str, Any], client: httpx.Client, reviewed: dict[str, str]) -> list[str]:
    """Pin every pending Hugging Face item in ``data``. Returns what changed."""
    from raiker.voice.catalogue import PERMISSIVE_LICENCES

    changes: list[str] = []
    revisions: dict[str, str] = {}
    for item in data["items"]:
        repo, path = item.get("hf_repo"), item.get("hf_path")
        if not repo or not path or not item.get("pending_reason"):
            continue
        revision = revisions.get(repo) or revisions.setdefault(repo, _revision(client, repo))
        sha256, size = _file_info(client, repo, revision, path)
        item["revision"] = revision
        item["url"] = f"{HF}/{repo}/resolve/{revision}/{quote(path)}"
        item["sha256"] = sha256
        item["size_bytes"] = size
        item.pop("approx_size_bytes", None)
        if item["id"] in reviewed:
            item["licence"] = reviewed[item["id"]]
        if item.get("licence") in PERMISSIVE_LICENCES:
            item.pop("pending_reason", None)
            changes.append(f"pinned {item['id']} at {revision[:12]} ({size} bytes)")
        else:
            item["pending_reason"] = (
                "Digest pinned; the licence still needs review under LICENSING_POLICY.md before this is offered."
            )
            changes.append(f"digest only for {item['id']} (licence {item.get('licence')!r} not reviewed)")
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--write", action="store_true", help="update the catalogue file")
    parser.add_argument("--licence-reviewed", action="append", default=[], metavar="ID=LICENCE")
    args = parser.parse_args(argv)
    reviewed = dict(entry.split("=", 1) for entry in args.licence_reviewed)
    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "Raiker"}) as client:
        changes = pin(data, client, reviewed)
    for line in changes:
        print(line)
    if args.write and changes:
        CATALOGUE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {CATALOGUE}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
