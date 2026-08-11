from __future__ import annotations

from raiker.app.tray import menu_state


def test_tray_menu_uses_host_state_as_its_single_source_of_truth() -> None:
    running = menu_state({"state": "running", "waiting": []})
    assert running.status_label == "Running"
    assert running.pause_label == "Pause"

    paused = menu_state({"state": "paused", "waiting": []})
    assert paused.status_label == "Paused"
    assert paused.pause_label == "Resume"

    attention = menu_state({"state": "needs attention", "waiting": [{"kind": "blocked_task"}]})
    assert attention.status_label == "Needs attention"
