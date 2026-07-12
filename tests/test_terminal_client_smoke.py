from __future__ import annotations

from raiker.cli.commands import handle_slash_command, submit_terminal_prompt
from raiker.cli.main import main


def test_raiker_dispatches_terminal_client(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--prompt", "/models"]) == 0
    assert "Model profiles" in capsys.readouterr().out


def test_terminal_prompt_simple_and_list_files(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    source_config = __import__("pathlib").Path(__file__).resolve().parents[1] / "config"
    for name in ["model-profiles.json", "channel-connectors.json"]:
        (tmp_path / "config" / name).write_text(
            (source_config / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    simple = submit_terminal_prompt("Hello Raiker", workspace_root=tmp_path)
    listing = submit_terminal_prompt("List files in this project", workspace_root=tmp_path)
    assert "model_unavailable: provider_connection_failed" in simple
    assert "model_unavailable: provider_connection_failed" in listing
    assert (tmp_path / ".raiker" / "events").exists()
    assert (tmp_path / ".raiker" / "checkpoints").exists()


def test_terminal_approval_and_registry_commands(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    source_config = __import__("pathlib").Path(__file__).resolve().parents[1] / "config"
    for name in ["model-profiles.json", "channel-connectors.json"]:
        (tmp_path / "config" / name).write_text(
            (source_config / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    approval = submit_terminal_prompt("!echo hi", workspace_root=tmp_path)
    assert "model_unavailable: provider_connection_failed" in approval
    assert "model_unavailable: provider_connection_failed" in approval
    assert "Apple Mobile App" in handle_slash_command("/channels", workspace_root=tmp_path)
    assert "raiker-local-llama-cpp" in handle_slash_command("/models", workspace_root=tmp_path)
    assert "unknown_model_profile:mock:anything" in handle_slash_command(
        "/launch --provider mock --model anything", workspace_root=tmp_path
    )
