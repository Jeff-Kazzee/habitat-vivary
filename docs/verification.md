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
The initial 21-file export passed a complete reachable-history credential
pattern scan and a separate private-path/account-marker check before its first push.

`scripts/verify-source.py` uses Docker Compose's parser to inspect the resolved
configuration. It does not contact a Docker daemon or start containers.
It also renders a small bind-policy probe through the same parser. This checks
how that Compose version represents false, true, and default host-path creation.
The actual project bind must match the distinct false case. Missing JSON fields
alone do not count as false. Neither parser invocation pulls an image or creates
the probe's host directory.
`scripts/test-cli.py` runs the command wrapper against a mock Docker executable.
It checks argument handling and dispatch without invoking real Docker.
`scripts/test-node-security.py` tests supported fixed versions, affected and
unsupported versions, malformed output, actual-executable query failures, and
the Docker build and startup guards. It also checks the supported lines' UTC
expiry boundaries, the current image pin's support status, and the incident-specific
CA package pins in both images. It downloads no runtime or dependency.
The startup check uses `/usr/local/bin/habitat-python`. The image creates this
link as root from `PYTHON_VERSION` and checks its version after installation.
This bypasses the mounted project's [mise Python selection](https://mise.jdx.dev/configuration.html).
A controlled shell fixture verifies that an unavailable project Python blocks
the old startup command but not the pinned interpreter. A failing Node guard
still blocks the requested command. These checks do not build the image.
The Source security workflow runs these three source checks on pull requests
and pushes to `main`. It does not build or publish an image.
Its first step is the complete inline reviewed PowerShell probe. Before checkout,
it finds the ancestor Runner.Worker and checks that worker's bundled node24
executable, without substituting PATH Node. An affected or unknown runtime,
migration override or runner hook fails the job before JavaScript actions run.
Source tests bind the inline bytes to the vetted canonical script and admit
only this reviewed native hosted job and immutable checkout action.

The pinned [checkout manifest](https://github.com/actions/checkout/blob/d23441a48e516b6c34aea4fa41551a30e30af803/action.yml)
uses node24 for main and post steps and has no pre hook. Run steps cannot
precede action pre hooks, runner job hooks, or early hashFiles evaluation.
Those provider boundaries remain outside this guard. There is no diagnostic
action that bypasses a failed probe, and CI must fail if the provider runtime
is below the security floor.

For the October 21 Node change, container-build and tool compatibility checks
remain pending. See [Node security verification](node-security.md) for the
archive-authentication prerequisite and publication limits.

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
