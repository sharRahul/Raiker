#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# GCR-02 — count the sockets a running `raiker-web` holds open.
#
# Provider validation used to construct a live provider and drop it, and both
# the Anthropic and OpenAI-compatible providers create an `httpx.AsyncClient`
# in `__post_init__` when none is supplied. Their execution methods close it in
# `finally`; the validation paths never did. So repeated model selection and
# launch validation left unclosed clients and their connection pools behind.
#
# The fix is a validation path that opens nothing, and this is how a live round
# measures it: take the count, drive the UI presses that used to leak, take it
# again. Growth across the run is the defect; a flat count is the fix.
#
#     scripts/live_socket_check.sh 8765          # print the count now
#     scripts/live_socket_check.sh 8765 before   # write /tmp/raiker-sockets.before
#     scripts/live_socket_check.sh 8765 after    # compare, and exit non-zero on growth
set -euo pipefail

PORT="${1:-8765}"
PHASE="${2:-print}"
STATE="/tmp/raiker-sockets.before"

# `ss -tlnp` is the obvious way to name the listener and is unavailable in some
# sandboxes (it prints nothing rather than failing), so the port is matched
# against the host's own command line. Both are tried, in that order.
pid="$(ss -tlnp 2>/dev/null | awk -v p=":${PORT}" '$4 ~ p {print $NF}' \
      | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2 || true)"
if [ -z "${pid}" ]; then
  pid="$(pgrep -f "raiker-web.*--port[= ]${PORT}|apps\.api\.main.*--port[= ]${PORT}" \
        | head -1 || true)"
fi
if [ -z "${pid}" ]; then
  echo "no raiker-web process found for port ${PORT}" >&2
  exit 2
fi

# Every socket the process holds, listening and connected alike. Counted from
# the process's own file descriptors rather than from `ss`, so a socket that is
# closed but not yet reaped by the kernel is not mistaken for a live one.
count="$(find "/proc/${pid}/fd" -type l -printf '%l\n' 2>/dev/null | grep -c '^socket:' || true)"

case "${PHASE}" in
  before) echo "${count}" > "${STATE}"; echo "sockets before: ${count}" ;;
  after)
    previous="$(cat "${STATE}" 2>/dev/null || echo 0)"
    echo "sockets before: ${previous}, after: ${count}"
    # A live round opens and closes real request sockets, so the bar is "did not
    # grow by a client per validation", not "identical". The old path leaked one
    # per press; this leaves generous headroom and still fails a regression.
    if [ "${count}" -gt "$(( previous + 8 ))" ]; then
      echo "open sockets grew by $(( count - previous )) across the run" >&2
      exit 1
    fi
    ;;
  *) echo "sockets: ${count}" ;;
esac
