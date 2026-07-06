# Constrain Egress & Inputs

> Best Practices › Egress & Inputs. Back to [Best Practices](best-practices.md).

- Off-machine model access, channels, and network capabilities are fail-closed
  until you set the relevant owner egress allowlist
  (`RAIKER_MODEL_EGRESS_ALLOWLIST`, `RAIKER_CHANNEL_EGRESS_ALLOWLIST`,
  `RAIKER_CONTAINER_IMAGE_ALLOWLIST`, `RAIKER_PLUGIN_RUNTIME_ALLOWLIST`, …). Keep
  them as small as possible; an empty allowlist denies everything.
- Treat model output and inbound channel/plugin content as **untrusted** — it can
  only ever resolve to allowlisted hosts and governed tools.
- Keep provider keys and allowlist values out of the UI and events.
