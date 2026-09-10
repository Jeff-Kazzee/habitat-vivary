#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
action="${1:-help}"
if (($#)); then shift; fi

case "$action" in
  help|-h|--help)
    printf '%s\n' 'Usage: bash habitat.sh check|build|start|shell|status|stop' \
      'Configure .env first. Run inside Linux with Docker Engine and Compose installed.'
    exit 0 ;;
  check|build|start|shell|status|stop) ;;
  *) printf 'Unknown action: %s\n' "$action" >&2; exit 2 ;;
esac
if (($#)); then
  printf '%s\n' 'Unexpected arguments. Use bash habitat.sh help.' >&2
  exit 2
fi
if [[ ! -f "$repo_dir/.env" ]]; then
  printf '%s\n' 'Missing .env. Copy .env.example to .env and set your project directory and name.' >&2
  exit 2
fi

compose=(docker compose --project-directory "$repo_dir" --env-file "$repo_dir/.env" -f "$repo_dir/compose.yaml")
case "$action" in
  check) "${compose[@]}" config --quiet ;;
  build) "${compose[@]}" build ;;
  start) "${compose[@]}" up -d --no-build ;;
  shell) "${compose[@]}" exec dev /bin/bash ;;
  status) "${compose[@]}" ps --all ;;
  stop) "${compose[@]}" down --timeout 10 ;;
esac
