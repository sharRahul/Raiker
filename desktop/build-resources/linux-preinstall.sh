#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# DIST-05 — the Linux packages' system check, run by dpkg/rpm before a file of
# Raiker is unpacked. The package manager already enforces the architecture,
# the libraries Raiker depends on, and the space the files take; this adds the
# floor `raiker/app/system_check.py` applies when Raiker starts, so a computer
# Raiker would refuse is told so now, and nothing is installed.
#
# It reads only /proc/meminfo, writes nothing, and never prompts: package
# managers may run it without a terminal.
set -e

min_mb=4096
good_mb=8192
mem_kb=$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo 2>/dev/null || true)
mem_kb=${mem_kb:-0}
mem_mb=$((mem_kb / 1024))

echo "Raiker: checking this computer before installing"
if [ "$mem_mb" -eq 0 ]; then
  echo "  memory: could not be measured; Raiker checks it again when it starts"
elif [ "$mem_mb" -lt "$min_mb" ]; then
  echo "  memory: ${mem_mb} MB. Raiker needs at least 4 GB of memory." >&2
  echo "Raiker was not installed: this computer does not meet its requirements." >&2
  exit 1
elif [ "$mem_mb" -lt "$good_mb" ]; then
  echo "  memory: ${mem_mb} MB. Enough for Raiker; local models need 8 GB or more."
else
  echo "  memory: ${mem_mb} MB"
fi
echo "Raiker: this computer can run Raiker. It finishes setting up the first time you open it."
exit 0
