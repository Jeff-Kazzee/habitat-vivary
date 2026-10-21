# Node security verification

The [October 21, 2026 Node advisory](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases)
fixes multiple issues, including Brotli remote code execution CVE-2026-111497.
The policy requires these minimum stable versions in supported release lines:

| Major | Minimum | Expires at 00:00 UTC |
| --- | --- | --- |
| 22 | 22.23.4 | 2027-04-30 |
| 24 | 24.22.1 | 2028-04-30 |
| 26 | 26.12.1 | 2029-04-30 |

Older releases in those lines, unsupported majors, prereleases, version ranges,
and malformed version output fail. Future supported-major additions require a
policy review. Each supported line fails on or after its UTC expiry date from
the [Node release schedule](https://github.com/nodejs/Release/blob/main/schedule.json).
The executable guard uses the current UTC date and accepts no CLI date override.
Source CI also checks the pinned image version against the current UTC date.
Passing this policy establishes the October 21 version floor.
It does not prove that no other vulnerability exists.

## Image pin and checks

Habitat preserves its Node 22 major and pins `22.23.4`. The Dockerfile rejects
other `NODE_VERSION` build arguments before downloading a runtime. It downloads
`node-v22.23.4-linux-x64.tar.xz` directly from `nodejs.org`, checks SHA-256 before
extraction, and checks `node --version` against the pin. Python then queries
the actual Node executable and applies the security policy before Corepack,
pnpm, or bundled agent tools run. The entrypoint repeats this policy before
executing the container command.

The [official release-page source](https://github.com/nodejs/nodejs.org/blob/main/apps/site/pages/en/blog/release/v22.23.4.md)
publishes this archive checksum:

```text
1805bcd35e6815559bd2eb97db438d3fdb0eb3a5e6a977b7c1badca76337e9ce  node-v22.23.4-linux-x64.tar.xz
```

The development image has a new tag, `2026-10-21-node22.23.4`. The proxy image
uses `2026-10-21-emudhra`. The ordinary `start` command still uses `--no-build`,
so neither service can silently select its old September-tagged image. This
source change does not update existing images or restart running containers.
Rebuild and verify both images separately before using them.

## Incident-specific system CA correction

Both Dockerfiles pin `ca-certificates=20260816ubuntu0.24.04.1`, replacing
`20260601~24.04.1`. [Ubuntu USN-8944-1](https://ubuntu.com/security/notices/USN-8944-1),
published October 20, identifies this exact Ubuntu 24.04 package as its eMudhra
incident update. It removes emSign ECC Root CA - G3 after the intermediate
certificate compromise. This is incident-specific evidence, not a latest-version
inference. Source CI checks both pins and rejects the old value.

The notice describes root removal. It does not establish exact-key denylisting
or rejection of every cross-sign path. Package authenticity, installed image
trust contents, and each client's actual trust backend remain unverified until
an isolated build and inspection. The Node guard does not protect other clients
such as curl, Git, Python, or the proxy. The first image build remains on hold
for the provenance prerequisite below. Verify the resulting image's package
and trust contents before allowing use.

## Verification still required before rebuilding

The source review used the archive checksum from the official release page.
It did not download or cryptographically authenticate the archive or its signed
checksum manifest. Follow Node's
[binary verification procedure](https://github.com/nodejs/node#verifying-binaries):
authenticate `SHASUMS256.txt.asc` with `gpgv` using a reviewed, pinned official
release keyring, then compare the exact archive checksum. Signed OIDC build
provenance remains unverified. GPG authentication must not silently replace
a separate provenance requirement. A policy exception, if needed, must name
this exact artifact and checksum.

After provenance review, build only in an isolated Linux environment without
credentials or private mounts. Verify the image's actual Node version, run the
policy check, and confirm pnpm, Claude Code, Codex, and Varlock still work.
Confirm Compose startup succeeds with the fixed image and an affected
`NODE_VERSION` override fails before allowing use or publication.
Do not start a stopped host daemon
as part of a source-only review.

## Scope of CI and publication

The Source security workflow runs policy regression tests, Compose validation,
and the existing Docker-stub command tests. No project package manifest or
lockfile exists in this repository. Global CLI dependencies are resolved during
the image build and remain outside a committed dependency lock. No dependency
audit or embedded-runtime assessment is claimed for those tools, Python, apt
packages, or the base image.

There is no automated image publisher or deployment workflow. CI does not
prevent an authorized user from building or publishing manually. A future image
publisher must depend on successful source tests, actual image-runtime checks,
and relevant dependency and provenance checks before publication. Branch protection
and manual-publication controls are separate administration decisions.
