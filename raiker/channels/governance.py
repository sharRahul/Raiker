from __future__ import annotations


def external_channel_activation_status(
    connector_id: str, paired: bool = False
) -> dict[str, object]:
    return {
        "connector_id": connector_id,
        "paired": paired,
        "active": False,
        "approval_relay_enabled": False,
        "reason": "phase4_external_channels_disabled_until_pairing_sender_trust_and_policy_complete",
    }
