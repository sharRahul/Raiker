"""Live proof gate for BUG-194 filtered command egress.

The product must not advertise ``filtered_network`` merely because a proxy was
configured.  This suite is intentionally skipped until the operator supplies a
running Docker/Podman boundary image and enables the dedicated CI job.  Unit
tests still cover policy, token, lifecycle and UI honesty; this file records
the exact missing proof rather than silently treating an absent daemon as a
pass.
"""

from __future__ import annotations

from raiker.execution.profiles import ExecutionProfile


def test_filtered_network_capability_requires_live_bypass_and_revocation_proof() -> None:
    profile = ExecutionProfile(
        "container_egress_requested",
        "container",
        runtime="docker",
        image="raiker-tools@sha256:" + "a" * 64,
        tools=("shell",),
        config={"egress_domains": ["api.example.com"], "egress_ports": [443]},
    )
    assert profile.features.filtered_network is False
