# Security and limits

Habitat restricts where project code runs and which files it can reach.
Treat the project directory, agent state, and permitted network destinations
as accessible to that code.

## Boundaries

- The development container mounts one project directory. Code can modify or
  delete files in that directory, including Git history and any secrets you put
  there. Do not mount your home directory or the Habitat checkout.
- The development container uses the non-root `ubuntu` user. Its root filesystem
  is read-only, capabilities are dropped, and privilege escalation is disabled.
  Writable project and authentication volumes remain writable.
- The Docker socket is not mounted. The container has no published ports and
  joins only an internal Docker network.
- The proxy joins that internal network and an outbound network. Squid permits
  selected destination domains on ports 80 and 443. It does not inspect HTTPS
  content or prevent data from being sent to an allowed domain. The broad
  provider domains in the default list can host user-controlled content.
- Named authentication volumes are separated by Compose project name. Reusing
  the name reuses that project's login state. A process inside the development
  container can read those credentials.
- WSL isolation depends on the host setup. The Compose file does not create a
  dedicated distribution or disable Windows integration. Linux kernel and
  container-runtime vulnerabilities remain outside these controls.

## Builds and dependencies

The runtime proxy does not govern image builds. Docker executes package
installation steps while building an image, with its own network access and
resource use. Inspect the Dockerfiles before building.

The Ubuntu base image, mise download, and Node archive have SHA-256 pins. The Dockerfiles pin
direct apt packages and tool versions, but they do not fully lock npm transitive
resolution or the Python download. The apt repository is a moving index,
so an older pinned package may become unavailable. A pin is not a malware audit.

Refresh pins deliberately. Review the upstream release and provenance, change
the relevant Dockerfile arguments or apt version, rebuild in a disposable Linux
environment, and repeat the first-build checks in [verification](verification.md).
Keep authentication volumes and private project files out of image builds.
The `.dockerignore` file permits only Dockerfiles, `squid.conf`, and the two
reviewed runtime-guard scripts in the build context.

Both images pin the incident-specific Ubuntu 24.04 CA package from
[USN-8944-1](https://ubuntu.com/security/notices/USN-8944-1). The notice documents
emSign ECC Root CA - G3 removal. Installed trust contents and coverage of other
certificate paths require separate image verification before use.

The [Node security policy](node-security.md) checks the actual `node` executable
before tool installation and container startup. It covers the declared Node
runtime. Native tools can embed separate runtimes, and project dependencies can
have their own vulnerabilities. These checks do not establish their safety.

## Sharing

Share this repository's source files. Do not share a WSL disk export, Docker
volume backup, account configuration, shell history, or project archive.
Use your own agent account and keep its normal permission prompts enabled.
Habitat includes no unattended agent launcher or automatic permission bypass.

No claim is made that Habitat safely contains arbitrary hostile code. For code
that may actively attack the environment, use a disposable VM or another
appropriately isolated host with no sensitive data or accounts.
