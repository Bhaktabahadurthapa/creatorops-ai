# Contributing to CreatorOps AI

Thank you for helping improve CreatorOps AI. Contributions should strengthen
the local idea-to-video workflow while protecting user media, voice references,
and API credentials.

## Before you start

- Read the [README](README.md) for setup and architecture details.
- Search existing issues and pull requests before opening a duplicate.
- Keep changes focused. Discuss large features in an issue before implementation.
- Never include API keys, private recordings, uploaded media, generated outputs,
  model downloads, or local environment files.

## Local setup

Follow [How to Run Locally](README.md#how-to-run-locally), then verify the
backend and frontend before making changes.

## Development checks

Run all relevant checks before opening a pull request:

```bash
cd backend
source .venv/bin/activate
pytest -v

cd ../frontend
npm run lint
npm run build
```

Video and voice tests must mock OpenAI, XTTS, HyperFrames, and FFmpeg unless a
manual smoke test is explicitly required. Unit tests must not call paid APIs,
load the XTTS model, or perform expensive video rendering.

## Pull requests

1. Create a focused branch from `main`.
2. Make the smallest complete change that solves the problem.
3. Add or update tests when behavior changes.
4. Update documentation when setup, endpoints, or user workflows change.
5. Confirm no secrets or private media are staged.
6. Explain what changed, why it changed, and how it was validated.

## Responsible voice use

Only contribute voice features that require a voice owned by the user or used
with explicit permission. Features designed for impersonation, deception, or
non-consensual voice cloning are outside this project's scope.

By participating, you agree to follow the
[Code of Conduct](CODE_OF_CONDUCT.md) and [Security Policy](SECURITY.md).
