# Installation

> Getting Started › Installation. Back to [Getting Started](getting-started.md).

Raiker targets **Python 3.11+**.

```bash
python3 -m pip install -e ".[dev]"
```

The `[dev]` extra pulls `pytest`, `ruff`, and `mypy` for development and the
local validation gate.

## The `cffi` note

If Ed25519 plugin-signature verification panics on import
(`ModuleNotFoundError: No module named '_cffi_backend'`), install `cffi`:

```bash
python3 -m pip install cffi
```

CI's fresh-runner install pulls `cffi` in transitively, so this is only needed
for some local setups.

## Next

- [Bootstrap the Owner](getting-started-bootstrap-owner.md)
