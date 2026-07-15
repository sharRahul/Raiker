# Quick Start Guide

Raiker is a governed AI agent runtime for secure, observable local automation.

## 1. Installation
```bash
git clone https://github.com/sharRahul/Raiker.git
cd Raiker
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## 2. Start Your Model
Raiker requires a model server. 
- **llama.cpp**: Default (port 8080)
- **Ollama**: `ollama serve`
- **LM Studio**: Start local server

## 3. First Prompt
```bash
raiker
# Inside client:
/model use raiker-local-llama-cpp
/model health
Hello Raiker!
```

## Next Steps
- [Detailed Setup](setup.md)
- [Model Configuration](models.md)
- [Using the Web Dashboard](interfaces.md)
- [Example Workflows](workflows.md)
- [Governance & Policy](governance.md)
- [Troubleshooting](troubleshooting.md)
