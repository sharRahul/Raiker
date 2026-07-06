# Channels

> Platform & Integrations › Channels. Back to [Platform & Integrations](platform-integrations.md).

The reference channel (`external_channel_runtime` + `channel_approval_relay`) is a
single-owner **outbound** bridge with a connector auth model and an owner egress
allowlist (`RAIKER_CHANNEL_EGRESS_ALLOWLIST`, empty = fail closed). Inbound
content is treated as untrusted and can only resolve to allowlisted hosts and
governed tools. See [`CHANNELS_SPEC.md`](../CHANNELS_SPEC.md).
