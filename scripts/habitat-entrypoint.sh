#!/usr/bin/env bash
set -euo pipefail

/usr/local/bin/habitat-python /usr/local/lib/habitat/check-node-security.py
exec "$@"
