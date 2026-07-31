# Changelog

All notable changes to CreatorOps AI are documented in this file.

## [1.0.0] - 2026-07-31

### Added

- Structured OpenAI script and scene generation.
- Authorized Chatterbox Turbo narration workflow.
- Uploaded and AI-generated visual support.
- Asynchronous voice and video jobs.
- FFmpeg rendering with motion, transitions, subtitles, branding and music.
- Next.js project and dashboard workflows.
- Docker-based GPU backend and Vercel frontend deployment paths.
- Pull-request CI for backend tests, frontend linting and production builds.

### Security

- Backend-only API credentials.
- File type, size, media stream and path validation.
- Private voice-reference and generated-media exclusions.
- Responsible-use guidance for authorized voices.

### Known limitations

- The public frontend requires a separately running HTTPS backend for generation.
- Jobs run in-process and do not resume after a backend restart.
- Authentication and multi-user isolation are not yet implemented.

[1.0.0]: https://github.com/Bhaktabahadurthapa/creatorops-ai/releases/tag/v1.0.0
