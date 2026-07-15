# System Setup

## Prerequisites
- **Python 3.11+**
- **Node 20+** (for web dashboard)
- **Git**

## Installation Detail
Follow the quickstart for basic installation. For development:
`python -m pip install -e ".[dev]"`

## Configuration
### Environment Variables
- `RAIKER_TUI=plain`: Use line-oriented shell.
- `RAIKER_WEB_UI_DIR=<path>`: Custom web UI directory (default: `apps/web/dist`).

### Workspace
Use `--workspace <path>` to define where runtime state is stored. Defaults to current directory.
