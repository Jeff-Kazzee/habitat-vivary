# Verification

Export date: 2026-09-10.

The original local Habitat sandbox was built and used for development. This
repository contains a generalized configuration with a different project mount,
explicit runtime limits, and a smaller command interface. Its complete image
build and first-run sequence have not been rerun for this export.

## Checks in this repository

The 2026-09-10 source check passed 59 assertions. All eight command-wrapper
tests passed using Git for Windows Bash and a mock Docker executable.
Independent source review found no blocking privacy or configuration issues.

`scripts/verify-source.py` uses Docker Compose's parser to inspect the resolved
configuration. It does not contact a Docker daemon or start containers.
`scripts/test-cli.py` runs the command wrapper against a mock Docker executable.
It checks argument handling and dispatch without invoking real Docker.

Before publication, scan every reachable Git blob for credentials. A clean
pattern scan is limited to the patterns it checks. These source checks do not
establish that an image build or a live agent login succeeds on another machine.

## First build on a new machine

1. Review the Dockerfiles and prepare a disposable project with no credentials.
2. Run `bash habitat.sh check`, `bash habitat.sh build`, and `bash habitat.sh start`.
   Confirm both images build and the proxy becomes healthy.
3. Run `bash habitat.sh shell`. Check `id -u`, `node --version`, `python --version`,
   `pnpm --version`, `claude --version`, and `codex --version`.
4. Confirm `/workspace/project` is the intended project. Create and remove a
   disposable file there. Verify it appears in the Linux project directory.
5. Confirm a write to `/` is refused and that `/var/run/docker.sock` is absent.
6. Test an allowed HTTPS destination through the configured proxy. Confirm a
   disallowed destination is denied. Confirm a direct connection without the
   proxy is refused. Do not infer all network paths from one successful check.
7. On the Linux host, inspect the two containers with `docker inspect` and
   `docker stats --no-stream`. Confirm memory, swap, CPU, process, mount,
   capability, and network settings match `compose.yaml`.
8. Run `bash habitat.sh stop`. Confirm this Compose project's containers are
   gone, while the project files and named volumes remain.

Sign in to an agent only after these checks pass. Native Linux and WSL2 hosts
have different outer boundaries. macOS, ARM emulation, GPU workloads, and
browser-preview forwarding are outside this export's verified scope.
