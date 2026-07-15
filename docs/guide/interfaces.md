# User Interfaces

## Terminal Client (`raiker`)
Standard line-oriented shell.
- **Usage**: `raiker` or `raiker --prompt "query"`
- **Commands**: Use `/help` for full catalog.

## Web Dashboard (`raiker-web`)
Single-user loopback interface (`127.0.0.1:8765`).

### Setup & Launch
```bash
npm --prefix apps/web install
npm --prefix apps/web run build
raiker-web --workspace .
```

### Dashboard Features
- **Live Stream**: Gather $\rightarrow$ Plan $\rightarrow$ Act $\rightarrow$ Verify loop.
- **Approval Queue**: Metadata-only resolution of gated actions.
- **Security Settings**: Step-up gated configuration.
- **STOP Switch**: Immediate runtime termination.
