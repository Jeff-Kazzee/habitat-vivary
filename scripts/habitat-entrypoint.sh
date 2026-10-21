#!/usr/bin/env bash
set -euo pipefail

python /usr/local/lib/habitat/check-node-security.py
exec "$@"
