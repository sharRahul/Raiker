# SPDX-License-Identifier: Apache-2.0
"""A loopback stand-in for the Ollama service, for live rounds on hosts without one.

Live rounds are run on hosts whose egress cannot fetch the Ollama installer or a
model's weights, and the behaviour a round has to prove — Raiker noticing that a
service is running, offering what it serves, checking the model the owner
chose, and following the service down and back up — is about the *service's
answers*, not about inference. This serves those answers on the same port and
paths Ollama does:

* ``GET /api/tags`` — the native catalogue Raiker's liveness probe reads;
* ``GET /v1/models`` — the OpenAI-compatible catalogue readiness checks read;
* ``POST /v1/chat/completions`` — streamed or not, answering with a sentence
  that names the model, so a turn's answer shows which model produced it.

It is not Ollama and a round that uses it says so. It binds loopback only.

    python scripts/live_ollama_standin.py --models llama3.2:3b,qwen3:8b \\
        --pidfile /tmp/standin.pid
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _handler(models: list[str]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib name
            stamp = time.strftime("%H:%M:%S")
            sys.stderr.write(f"{stamp} ollama-standin " + format % args + "\n")

        def _json(self, code: int, body: object) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 - stdlib name
            if self.path.startswith("/api/version"):
                self._json(200, {"version": "standin"})
            elif self.path.startswith("/api/tags"):
                self._json(
                    200,
                    {"models": [{"name": name, "model": name, "size": 0} for name in models]},
                )
            elif self.path.startswith("/v1/models"):
                self._json(
                    200,
                    {
                        "object": "list",
                        "data": [{"id": name, "object": "model", "owned_by": "library"} for name in models],
                    },
                )
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib name
            length = int(self.headers.get("Content-Length") or 0)
            request = json.loads(self.rfile.read(length) or b"{}")
            if not self.path.startswith("/v1/chat/completions"):
                self._json(404, {"error": "not found"})
                return
            model = str(request.get("model", ""))
            if model not in models:
                self._json(404, {"error": {"message": f'model "{model}" not found, try pulling it first'}})
                return
            text = f"Hello from {model}, answering through the local Ollama stand-in."
            usage = {"prompt_tokens": 20, "completion_tokens": len(text.split()), "total_tokens": 20 + len(text.split())}
            if not request.get("stream"):
                self._json(
                    200,
                    {
                        "id": "chatcmpl-standin",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                        "usage": usage,
                    },
                )
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for index, word in enumerate(text.split(" ")):
                chunk = {
                    "id": "chatcmpl-standin",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"index": 0, "delta": {"role": "assistant", "content": word if index == 0 else f" {word}"}, "finish_reason": None}],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            done = {
                "id": "chatcmpl-standin",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": usage,
            }
            self.wfile.write(f"data: {json.dumps(done)}\n\ndata: [DONE]\n\n".encode())
            self.wfile.flush()

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--models", default="llama3.2:3b,qwen3:8b")
    parser.add_argument("--pidfile", type=Path, default=None)
    args = parser.parse_args(argv)
    models = [name.strip() for name in args.models.split(",") if name.strip()]
    server = ThreadingHTTPServer(("127.0.0.1", args.port), _handler(models))
    if args.pidfile is not None:
        args.pidfile.write_text(str(os.getpid()), encoding="utf-8")
    try:
        server.serve_forever()
    finally:
        if args.pidfile is not None:
            args.pidfile.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
