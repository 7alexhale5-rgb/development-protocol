#!/usr/bin/env bash
# Private-data scan. Usage: bash tests/sanitization.sh [path ...]
exec python3 "$(cd "$(dirname "$0")" && pwd)/scan_private.py" "$@"
