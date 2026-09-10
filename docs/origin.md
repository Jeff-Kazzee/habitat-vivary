# Origin

Habitat began as a local development sandbox assembled with Codex in August
2026. It combines existing software: WSL2, Ubuntu, Docker Engine, and Squid.
The name identifies that configuration and its control scripts.

This standalone export was prepared on 2026-09-10. It retains the original
Dockerfile dependency pins and proxy allowlist. The export replaces personal
project mounts with one configurable project directory, adds explicit runtime
resource limits, and uses a smaller command wrapper.

The original application's source, machine build receipts, account state,
private paths, and project-specific launchers are not part of this repository.
No upstream project named Habitat is vendored here.

## Upstream components

- [Windows Subsystem for Linux](https://github.com/microsoft/WSL)
- [Ubuntu container image](https://hub.docker.com/_/ubuntu)
- [Docker Engine](https://docs.docker.com/engine/)
- [Docker Compose](https://github.com/docker/compose)
- [Squid](https://www.squid-cache.org/)
- [mise](https://github.com/jdx/mise)
- [Node.js](https://nodejs.org/)
- [Python](https://www.python.org/)
- [pnpm](https://pnpm.io/)
- [Codex CLI](https://github.com/openai/codex)
- [Claude Code](https://code.claude.com/docs/)
- [Varlock](https://varlock.dev/)

These components retain their own licenses and terms. The repository does not
contain their installed packages, image layers, or account credentials.
