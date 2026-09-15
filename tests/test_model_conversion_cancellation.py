"""A conversion answers Cancel while it is running (GCR-24).

The finding was not that Cancel was missing — it was that it was checked at two
instants with two blocking containers in between, under a six-hour isolation
budget. So "cancelled" could sit unanswered, with the CPU committed, for the
rest of the day.

These run the real ``Popen`` loop against a stand-in ``docker`` on PATH, because
the defect lived in *how the child was waited on*: a test that stubs the runner
proves the caller and leaves the wait exactly as it was.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from raiker.models.conversion import (
    CANCEL_POLL_SECONDS,
    ConversionCancelled,
    ConversionPreview,
    ConversionRefused,
    DockerConversionRunner,
    ModelConversionService,
    conversion_container_names,
    docker_command_plan,
)

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="the stand-in docker is a POSIX shim"
)


def _preview(tmp_path: Path, quantization: str = "Q4_K_M") -> ConversionPreview:
    source = tmp_path / "snapshot"
    source.mkdir(parents=True, exist_ok=True)
    (source / "config.json").write_text(
        json.dumps({"architectures": ["Qwen2ForCausalLM"]}), encoding="utf-8"
    )
    (source / "model.safetensors").write_bytes(b"safe")
    output = tmp_path / "output"
    output.mkdir(parents=True, exist_ok=True)
    return ModelConversionService().preview(source, output, "a" * 40, quantization)


def _fake_docker(directory: Path, body: str) -> None:
    """A `docker` on PATH that behaves however the test needs it to.

    Written in Python and invoked through this interpreter, so it runs the same
    way wherever the suite does and needs no shell.
    """
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "docker"
    script.write_text(f"#!{sys.executable}\nimport sys, time\n{body}\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class TestCancelReachesARunningConversion:
    def test_a_long_step_is_stopped_rather_than_waited_out(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The step would run for an hour; the cancellation lands in seconds.

        The assertion that matters is not the exception — it is that the call
        returns at all. Before this, `subprocess.run` held the worker until the
        child exited, so this test would have taken an hour.
        """
        bin_dir = tmp_path / "bin"
        stopped = tmp_path / "stopped.txt"
        _fake_docker(
            bin_dir,
            "if sys.argv[1] == 'stop':\n"
            f"    open({str(stopped)!r}, 'a').write(sys.argv[-1] + '\\n')\n"
            "    sys.exit(0)\n"
            "time.sleep(3600)\n",
        )
        monkeypatch.setenv("PATH", str(bin_dir))
        preview = _preview(tmp_path)

        with pytest.raises(ConversionCancelled):
            DockerConversionRunner().run(preview, should_cancel=lambda: True)

        # And it stopped the *container*, not only the client waiting on it.
        # Killing `docker run` alone leaves the work running with nothing
        # watching it, which is the worst of the three outcomes.
        assert stopped.read_text().strip() == conversion_container_names(preview)[0]

    def test_a_cancellation_is_not_reported_as_a_failed_conversion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bin_dir = tmp_path / "bin"
        _fake_docker(bin_dir, "if sys.argv[1] == 'stop':\n    sys.exit(0)\ntime.sleep(3600)\n")
        monkeypatch.setenv("PATH", str(bin_dir))

        with pytest.raises(ConversionCancelled) as raised:
            DockerConversionRunner().run(_preview(tmp_path), should_cancel=lambda: True)

        assert str(raised.value) == "conversion_cancelled_by_owner"
        # A subclass, so an older caller that only knows about refusals still
        # catches it — and a caller that cares can tell them apart.
        assert isinstance(raised.value, ConversionRefused)

    def test_the_isolation_deadline_is_its_own_answer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A step that overruns says so, rather than reading as a broken model."""
        bin_dir = tmp_path / "bin"
        _fake_docker(bin_dir, "if sys.argv[1] == 'stop':\n    sys.exit(0)\ntime.sleep(3600)\n")
        monkeypatch.setenv("PATH", str(bin_dir))
        preview = _preview(tmp_path)
        object.__setattr__(preview.isolation, "timeout_seconds", 0)

        with pytest.raises(ConversionRefused) as raised:
            DockerConversionRunner().run(preview, should_cancel=lambda: False)

        assert str(raised.value) == "isolated_conversion_timed_out"
        assert not isinstance(raised.value, ConversionCancelled)

    def test_a_step_that_fails_is_still_a_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bin_dir = tmp_path / "bin"
        _fake_docker(bin_dir, "sys.exit(3)\n")
        monkeypatch.setenv("PATH", str(bin_dir))

        with pytest.raises(ConversionRefused) as raised:
            DockerConversionRunner().run(_preview(tmp_path), should_cancel=lambda: False)

        assert str(raised.value) == "isolated_conversion_failed"
        assert not isinstance(raised.value, ConversionCancelled)

    def test_the_flag_is_read_on_a_cadence_rather_than_at_the_two_ends(self) -> None:
        assert 0 < CANCEL_POLL_SECONDS <= 5


class TestTheContainerHasARecoverableIdentity:
    def test_each_step_runs_under_a_name_cancel_can_reach(self, tmp_path: Path) -> None:
        preview = _preview(tmp_path)
        convert, quantize = docker_command_plan(preview, "docker")
        convert_name, quantize_name = conversion_container_names(preview)

        assert convert[convert.index("--name") + 1] == convert_name
        assert quantize[quantize.index("--name") + 1] == quantize_name
        assert convert_name != quantize_name

    def test_the_names_are_derived_from_the_preview_so_they_can_be_recomputed(
        self, tmp_path: Path
    ) -> None:
        """Deterministic rather than random, which is what makes it recoverable.

        The preview is what is persisted with the operation, so a cleanup after
        a host restart can work out which containers this conversion started
        without a second stored identity that could drift from the first.
        """
        assert conversion_container_names(_preview(tmp_path / "a")) == conversion_container_names(
            _preview(tmp_path / "a")
        )

    def test_two_conversions_an_owner_could_run_at_once_do_not_collide(
        self, tmp_path: Path
    ) -> None:
        first = conversion_container_names(_preview(tmp_path / "one", "Q4_K_M"))
        second = conversion_container_names(_preview(tmp_path / "one", "Q6_K"))
        third = conversion_container_names(_preview(tmp_path / "two", "Q4_K_M"))

        assert len({first, second, third}) == 3

    def test_a_name_is_one_docker_will_accept(self, tmp_path: Path) -> None:
        import re

        for name in conversion_container_names(_preview(tmp_path)):
            assert re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]+", name), name
