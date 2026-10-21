# Habitat Vivary

A local sandbox for coding with Claude Code, Codex CLI, and other command-line
tools. Run it in a dedicated Linux environment. On Windows, use WSL2.

Habitat puts your project in a Docker container with a read-only root filesystem,
an editable project folder, persistent agent login volumes, and a network proxy
with an explicit domain allowlist. It includes Node, Python, pnpm, and Varlock.

This is a standalone export of the development sandbox used for Vivary.
You can use it with another project. It includes no Vivary application code,
accounts, project history, or prebuilt images.

## Start here

You need an **amd64 Linux machine or dedicated WSL2 distribution**, Git, Docker
Engine, and Docker Compose v2. The container user has UID/GID 1000. Your project
folder must be writable by that user. Start with [Windows setup](docs/windows-setup.md)
if you do not have the Linux environment yet.

Run these commands inside Linux:

```bash
git clone https://github.com/Jeff-Kazzee/habitat-vivary.git
cd habitat-vivary
cp .env.example .env
```

Edit `.env` and set two values:

```dotenv
COMPOSE_PROJECT_NAME=habitat-my-project
HABITAT_PROJECT_DIR=/home/your-user/work/my-project
```

Use an existing project directory on the Linux filesystem. Keep the Habitat
checkout outside that directory so project code cannot edit its container
configuration. Pick a different Compose project name for each project to give
it separate containers, networks, and login volumes.

```bash
bash habitat.sh check
bash habitat.sh build
bash habitat.sh start
bash habitat.sh shell
```

Build reads the Dockerfiles and downloads their dependencies. Review those files
first. Build-time downloads do not pass through the runtime allowlist proxy.
The shell opens at `/workspace/project`, where your chosen folder is mounted.

## Use your agents

Run `claude` or `codex` from the container shell and sign in with your own
account. No account or API subscription is included. Login files persist in
Docker volumes. Project code running as the same container user can read them,
so use an account whose access you are comfortable giving that code.

Agent permission prompts stay enabled. Habitat does not automatically approve
commands or launch autonomous work. Files you edit under `/workspace/project`
persist in your Linux project folder. Other writable caches under `/tmp` are
temporary.

## Stop when finished

Exit the container shell, then run:

```bash
bash habitat.sh stop
```

This removes this Compose project's containers and networks. It keeps your
project files and login volumes. `bash habitat.sh status` shows the containers
without starting them. On Windows, you can then stop your dedicated WSL
distribution as described in the setup guide.

## What the sandbox permits

| Resource | Default |
| --- | --- |
| Project files | One selected directory mounted read/write |
| Agent state | Separate named volumes for Claude, Codex, and Varlock |
| Development container | 2 GiB RAM, no extra swap, 2 CPUs, 256 processes |
| Proxy container | 256 MiB RAM, no extra swap, 0.5 CPU, 64 processes |
| Network | Internal project network, outbound proxy with a domain allowlist |
| Host exposure | No Docker socket, privileged mode, or published ports |
| Restart | Explicit start required |

The memory caps apply to running containers. Docker builds, the Docker daemon,
and WSL have separate overhead. Read [security and limits](docs/security.md)
before using Habitat with unfamiliar code. A container and a domain allowlist
do not provide complete protection against malicious code or data disclosure.

## Change the network allowlist

Edit `squid.conf`, then rebuild and start the services:

```bash
bash habitat.sh build
bash habitat.sh start
```

Allow only domains your workflow needs. The default list covers the bundled
agent providers, package registries, and GitHub. Access to a domain also permits
sending data to it. No ports are published for browser previews in this export.

## Maintain or inspect the source

```bash
python3 scripts/verify-source.py
python3 scripts/test-cli.py
python3 scripts/test-node-security.py
```

These checks validate configuration and command dispatch without starting a
container. See [verification](docs/verification.md) for what was checked and the
remaining first-build checks. The Dockerfiles retain dependency pins from the
original sandbox. Old apt versions can leave repository indexes, and exact
top-level versions do not lock every transitive dependency.

The development image now pins Node 22.23.4 and its official Linux x64 archive
checksum. Its build rejects version overrides and checks the actual executable
before installing tools. Its entrypoint repeats that check before starting the
container command. Both images use new tags and the incident-specific Ubuntu CA
package pin. Rebuild both rather than reusing the September images. Existing
running containers are unchanged.
Read [Node security verification](docs/node-security.md) before rebuilding.

The [codebase map](codebase-map.html) explains the files and how they fit together.
