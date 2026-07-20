# Security Policy

CreatorOps AI processes API credentials, private voice references, uploaded
media, and generated files. Security reports are taken seriously.

## Supported versions

| Version | Supported |
| --- | --- |
| Latest commit on `main` | Yes |
| Older commits and forks | No |

## Reporting a vulnerability

Do not open a public issue for a vulnerability or accidentally exposed secret.
Contact the repository owner privately through their GitHub profile and include:

- A clear description of the issue.
- Steps to reproduce it safely.
- The affected endpoint, file, or commit.
- The potential impact.
- A suggested fix, if available.

Do not include real API keys, private recordings, or sensitive uploaded media in
the report. Use redacted examples and minimal test files.

## Security expectations

- Keep `backend/.env` and `frontend/.env.local` out of Git.
- Keep private voice references, uploads, generated audio, and generated video
  out of Git.
- Never expose `OPENAI_API_KEY` through frontend code or `NEXT_PUBLIC_*`
  variables.
- Validate uploaded file types, sizes, media streams, filenames, and paths.
- Use only voices owned by the user or used with explicit authorization.
- Keep unit tests isolated from real OpenAI, XTTS, HyperFrames, and FFmpeg work.

## Disclosure

Please allow maintainers reasonable time to investigate and publish a fix
before sharing vulnerability details publicly.
