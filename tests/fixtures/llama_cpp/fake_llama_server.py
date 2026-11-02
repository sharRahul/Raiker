"""A stand-in ``llama-server``: the HTTP surface Raiker uses, and its failure modes.

Behaviour is chosen by the model file's name, so a test picks a scenario by
naming the file:

* ``*oom*``     — with ``-ngl`` above 16, prints a CUDA out-of-memory line and exits 1.
* ``*broken*``  — prints an unknown-architecture error and exits 1.
* ``*slow*``    — answers ``/health`` with 503 for the first second (loading).
* ``*crash*``   — exits with status 3 two seconds after becoming ready.

``--version`` and ``--list-devices`` answer like the real binary.
"""

from __future__ import annotations

import contextlib
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _arg(argv: list[str], *names: str, default: str = "") -> str:
    for index, item in enumerate(argv):
        if item in names and index + 1 < len(argv):
            return argv[index + 1]
    return default


def main(argv: list[str]) -> int:
    if "--version" in argv:
        print("version: 9999 (fake)\nbuilt with test", file=sys.stderr)
        return 0
    if "--list-devices" in argv:
        print("Available devices:\n  CUDA0: Fake GPU (8192 MiB, 7000 MiB free)")
        return 0
    port = int(_arg(argv, "--port", default="8080"))
    alias = _arg(argv, "--alias", default="local-gguf")
    model = _arg(argv, "--model", "-m")
    ngl = int(_arg(argv, "-ngl", "--n-gpu-layers", default="0"))
    ctx = int(_arg(argv, "-c", "--ctx-size", default="0"))
    name = model.lower()
    print(f"main: loading model {model} ngl={ngl} ctx={ctx}", flush=True)
    if "oom" in name and ngl > 16:
        print("ggml_cuda_init: CUDA error: out of memory", flush=True)
        return 1
    if "broken" in name:
        print("llama_model_load: error loading model: unknown model architecture: 'fake'", flush=True)
        return 1
    started = time.monotonic()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            return

        def _json(self, code: int, payload: object) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            loading = "slow" in name and time.monotonic() - started < 1.0
            if self.path == "/health":
                self._json(503 if loading else 200, {"status": "loading" if loading else "ok"})
            elif self.path == "/v1/models":
                self._json(200, {"data": [{"id": alias}]})
            else:
                self._json(404, {})

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length) or b"{}")
            last = request.get("messages", [{}])[-1].get("content", "")
            self._json(200, {
                "choices": [{
                    "message": {"role": "assistant", "content": f"echo:{last} model={alias} ngl={ngl} ctx={ctx}"},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5},
            })

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if "crash" in name:
        def crash() -> None:
            time.sleep(2.0)
            print("fatal: simulated crash", flush=True)
            import os

            os._exit(3)

        threading.Thread(target=crash, daemon=True).start()
    print(f"main: server is listening on http://127.0.0.1:{port}", flush=True)
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
