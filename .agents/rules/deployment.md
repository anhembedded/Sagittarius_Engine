---
name: Deployment
description: How the engine itself is published, and how a consuming app deploys.
trigger: model_decision
---

# Rules: Deployment

Merged 2026-08-23 from `context/deployment.md` (which duplicated this file — a stub — with
the only real content). One home now, not two.

## Distributing the engine (PyPI)

1. Bump the version in `pyproject.toml`.
2. Build: `python -m build`
3. Check the built artifact before uploading: `twine check dist/*` (this is exactly what
   `.github/workflows/ci.yml`'s `package` job runs — see `context/build.md`).
4. Publish: `twine upload dist/*`

## Deploying a consuming application

The engine has no opinion here — applications own their own deployment, same as they own
their own architecture. Common patterns already used in this repo's own reference consumers:

- **Docker**: containerize the app, run it as the entrypoint.
- **systemd**: run a long-lived bot or API server as a daemon process.
- **PyInstaller**: package a desktop UI tool (e.g. `tools/audit_dashboard`) as a standalone
  executable.
