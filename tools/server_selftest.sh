#!/usr/bin/env bash
#
# server_selftest.sh - Exercise the practice server end to end WITHOUT root.
# See tools/server_selftest.py for what is checked.
#
#   bash tools/server_selftest.sh

exec python3 "$(dirname "$0")/server_selftest.py" "$@"
