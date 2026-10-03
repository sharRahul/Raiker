# SPDX-License-Identifier: Apache-2.0
"""Seed real image generations into a live workspace for a Design round.

The image providers are unreachable from the hosts these rounds run on, so a
round that is about what Design does *with* pictures — the canvas, filing,
export, delete and restore — seeds them here instead. Everything the page reads
is still real: a real attachment holding real PNG bytes, and rows written by
the store's own method, read back through ``GET /api/images``. Nothing here is
reachable from the product; it is a harness for live rounds only.

    python scripts/seed_design_assets.py /tmp/raiker-live --project <project_id>

Prints the seeded generation ids as JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

from raiker.contracts.ids import new_id
from raiker.storage.sqlite import SQLiteStore


def _png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """A solid-colour PNG, built by hand so the seed needs no imaging library."""
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _owner(store: SQLiteStore) -> str:
    for account in store.list_accounts():
        principal = getattr(account, "principal_id", None) or (
            account.get("principal_id") if isinstance(account, dict) else None
        )
        if principal:
            return str(principal)
    raise SystemExit("No owner account in this workspace yet; sign in first.")


def seed(workspace: Path, project_id: str | None) -> list[str]:
    store = SQLiteStore(workspace)
    owner = _owner(store)
    made: list[str] = []

    def picture(prompt: str, rgb: tuple[int, int, int], *, source: str | None, project: str | None) -> str:
        data = _png(256, 256, rgb)
        generation_id = new_id("img_")
        attachment_id = new_id("att_")
        store.save_attachment(
            attachment_id=attachment_id,
            kind="generated_image",
            filename=f"{generation_id}.png",
            media_type="image/png",
            sha256=hashlib.sha256(data).hexdigest(),
            data=data,
            owner_principal_id=owner,
        )
        store.record_image_generation(
            generation_id=generation_id,
            owner_principal_id=owner,
            profile_id="openai-hosted",
            provider="openai",
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            status="ok",
            attachment_id=attachment_id,
            media_type="image/png",
            byte_size=len(data),
            source_generation_id=source,
            kind="edit" if source else "create",
            project_id=project,
        )
        made.append(generation_id)
        return generation_id

    origin = picture("A lighthouse at dusk, oil painting", (52, 84, 140), source=None, project=project_id)
    picture("The same lighthouse with a red lantern room", (160, 60, 52), source=origin, project=project_id)
    picture("A loose sketch of a harbour", (120, 120, 112), source=None, project=None)
    return made


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--project", default=None)
    arguments = parser.parse_args()
    print(json.dumps(seed(arguments.workspace, arguments.project)))


if __name__ == "__main__":
    main()
