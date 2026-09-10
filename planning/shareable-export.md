# Shareable Habitat export

Status: source prepared; publication pending
Date: 2026-09-10

## Request

Create a separate public GitHub repository named `habitat-vivary` that a friend
can use. Preserve the existing local sandbox.

## Done condition

- Publish generic Dockerfiles, a single-project Compose configuration, an
  allowlist proxy, and setup instructions without personal data or credentials.
- Validate the Compose configuration and command wrapper, review the export,
  and scan every reachable Git blob before pushing.
- Verify the public remote and record the exact limits of runtime validation.

## Scope

This repository exports the local sandbox configuration. It does not include
application code, agent state, image layers, personal build logs, or a WSL disk.
No existing sandbox is reconfigured or started to prepare this export.

## Verification

- 59 configuration assertions passed using Docker Compose's daemon-free parser.
- Eight command-wrapper tests passed with a mock Docker executable.
- Independent source review found no blocking privacy or configuration issue.
- A fresh image build and live first-run sequence remain unrun for this export.
