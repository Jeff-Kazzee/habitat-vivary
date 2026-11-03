# Habitat maintenance

This repository contains a reusable sandbox configuration, not user projects or
agent state. Keep project paths configurable and mount only one project per
Compose project name. Preserve the read-only root, capability restrictions,
resource limits, and internal network.

Run `python3 scripts/verify-source.py` and `python3 scripts/test-cli.py` after
changing configuration or command dispatch. These are source checks. Image
builds, authentication, networking, and volume behavior require separate runtime
verification in an isolated Linux environment.

Do not commit `.env`, agent login files, session transcripts, disk images,
project archives, or personal machine history. Scan the complete Git history
before publication. Refresh dependency pins deliberately and document any
verification that was not run.

Keep `codebase-map.html` and the setup instructions consistent with the files.

## Git

- Follow the Git law in Jeff's `~/AGENTS.md` (2026-11-03). `prod` is the default branch and the finished product. All work happens on `dev`. Branch `task/<id>-<slug>` from `origin/dev`, open the PR into `dev`, never push or force-push `prod`, `main` or `dev`, and end every commit with `Task:`, `Agent:` and `Agent-Session:` trailers. `prod` changes only through a promotion PR from `dev`, and every merge waits for Jeff's approval.
