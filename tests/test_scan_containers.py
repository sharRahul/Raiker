"""DEC-24 step 7 — a change that weakens a container Raiker builds fails.

The container definitions are read for the properties the sandbox and the
egress proxy depend on: digest-pinned bases, a non-root final user, nothing
fetched by ADD or piped into a shell, and no credential baked into a layer.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("scan_containers", ROOT / "scripts" / "scan_containers.py")
assert _SPEC is not None and _SPEC.loader is not None
scan_containers = importlib.util.module_from_spec(_SPEC)
sys.modules["scan_containers"] = scan_containers
_SPEC.loader.exec_module(scan_containers)

PINNED = "FROM python:3.13-slim@sha256:" + "a" * 64


def _rules(text: str) -> list[str]:
    return [p.rule for p in scan_containers.scan_definition("Containerfile", text)]


def test_a_pinned_non_root_definition_passes() -> None:
    assert _rules(f"{PINNED}\nRUN useradd app\nUSER app\n") == []


def test_a_tag_is_not_a_pin() -> None:
    assert _rules("FROM python:3.13-slim\nUSER app\n") == ["base_not_pinned"]


def test_an_image_that_never_leaves_root_fails() -> None:
    assert _rules(f"{PINNED}\nRUN true\n") == ["runs_as_root"]
    assert _rules(f"{PINNED}\nUSER app\nUSER root\n") == ["runs_as_root"]
    assert _rules(f"{PINNED}\nUSER 0:0\n") == ["runs_as_root"]


def test_each_stage_starts_again_as_its_base_images_user() -> None:
    text = f"{PINNED} AS build\nUSER app\nFROM build\nRUN make\n"
    # The second stage inherits nothing about USER from the line above it.
    assert _rules(text) == ["runs_as_root"]


def test_a_later_stage_may_build_from_an_earlier_one_without_a_digest() -> None:
    text = f"{PINNED} AS build\nRUN make\nFROM build\nUSER app\n"
    assert _rules(text) == []


def test_fetching_at_build_time_fails() -> None:
    text = (
        f"{PINNED}\nADD https://example.com/tool.tgz /opt/\n"
        "RUN curl -fsSL https://example.com/install.sh \\\n  | sh\nUSER app\n"
    )
    assert _rules(text) == ["add_from_url", "pipe_to_shell"]


def test_a_credential_baked_into_a_layer_fails_and_a_name_alone_does_not() -> None:
    assert _rules(f"{PINNED}\nENV GITHUB_TOKEN=abc123\nUSER app\n") == ["credential_in_image"]
    assert _rules(f"{PINNED}\nARG API_KEY\nUSER app\n") == []


def test_the_repositorys_own_definitions_pass() -> None:
    names = scan_containers.definitions(ROOT)
    assert names, "the sandbox and proxy definitions are expected to be found"
    for name in names:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert scan_containers.scan_definition(name, text) == [], name
