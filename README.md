<p align="center">
  <img src="docs/images/creatorops-ai-logo.svg" width="112" alt="CreatorOps AI logo">
</p>

<h1 align="center">CreatorOps AI</h1>

<p align="center"><strong>Your idea. Your voice. Your finished video.</strong></p>

<p align="center">
  Turn one concept into a structured script, authorized narration, AI-generated or uploaded visuals,<br>
  subtitles, and an export-ready HD video.
</p>

<p align="center">
  <a href="https://creatorops-ai-one.vercel.app"><strong>Live Frontend</strong></a> ·
  <a href="https://youtu.be/cPOUEL0nrMI"><strong>Demo Video</strong></a> ·
  <a href="docs/VAST_DEPLOYMENT.md">GPU Backend Guide</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-8b5cf6" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/Next.js-16-020617" alt="Next.js 16">
  <img src="https://img.shields.io/badge/FastAPI-Python_3.10%2B-009688" alt="FastAPI and Python 3.10 or newer">
  <img src="https://img.shields.io/badge/OpenAI-Responses_%2B_Image_API-10a37f" alt="OpenAI APIs">
  <img src="https://img.shields.io/badge/voice-Chatterbox_Turbo-7c3aed" alt="Chatterbox Turbo">
  <img src="https://img.shields.io/badge/video-FFmpeg-007808" alt="FFmpeg video rendering">
</p>

<p align="center">
  <a href="#demo">Demo</a> ·
  <a href="#system-flow">System flow</a> ·
  <a href="#features">Features</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#deployment-modes">Deployment</a> ·
  <a href="#how-to-run-locally">Local setup</a> ·
  <a href="#testing">Testing</a>
</p>

---

## Demo

### Video walkthrough

[![Watch the CreatorOps AI demo](https://img.youtube.com/vi/cPOUEL0nrMI/maxresdefault.jpg)](https://youtu.be/cPOUEL0nrMI)

**YouTube:** https://youtu.be/cPOUEL0nrMI

The demo shows the complete workflow:

```text
Idea
→ GPT-5.6 structured script
→ Authorized Chatterbox Turbo narration
→ Uploaded media or AI-generated visuals
→ Motion, transitions and subtitles
→ GPU-backed FFmpeg rendering
→ Final MP4 and SRT
→ Projects and Dashboard
```

### Live frontend

**Vercel:** https://creatorops-ai-one.vercel.app

> The frontend is deployed on Vercel. Full script, voice, image and video generation
> requires a reachable FastAPI backend. The backend can run locally or on a temporary
> Vast.ai GPU instance. GPU instances may be stopped outside demonstrations to control cost.

---

## System flow

<p align="center">
  <a href="docs/images/creatorops-ai-system-flow.png">
    <img src="docs/images/creatorops-ai-system-flow.png" width="100%" alt="CreatorOps AI end-to-end system flow">
  </a>
</p>

<p align="center"><sub>Idea → Script → Voice → Visuals → Video → Project</sub></p>

CreatorOps AI is a full-stack AI video-production platform built with Next.js,
FastAPI, OpenAI, Chatterbox Turbo and FFmpeg. It supports both local development
and a cloud demo architecture with a Vercel frontend and a GPU-backed FastAPI service.

| Start with | CreatorOps AI handles | Export |
| --- | --- | --- |
| Idea, platform, tone and duration | Script, scene timing, authorized narration, visuals, motion, subtitles, logo and music | 720p or 1080p MP4 plus SRT |

> [!IMPORTANT]
> API keys, private voice references, uploaded media and generated files are excluded
> from Git. In local mode they remain on the developer machine. In cloud mode they remain
> inside the configured backend data directory or attached persistent volume.

---

## The problem

Creating a professional short video normally requires several disconnected tools:

1. Write and organize a script.
2. Record or generate narration.
3. Collect images and clips.
4. Create or source missing scene visuals.
5. Animate static assets.
6. Generate and synchronize subtitles.
7. Add branding and music.
8. Render, export and organize the final files.

This workflow is slow and repetitive for solo creators, small businesses, agencies,
educators and internal marketing teams.

## The solution

CreatorOps AI combines the complete workflow in one application:

- Generates a validated script and timed scene plan with the OpenAI Responses API.
- Generates authorized narration with Chatterbox Turbo.
- Accepts uploaded images, videos, logos and background music.
- Generates text-free scene visuals with the OpenAI Image API.
- Animates still images with zoom, pan, fades and crossfades.
- Synchronizes scenes with narration and subtitles.
- Exports 720p or 1080p MP4 plus SRT subtitles.
- Tracks draft, voice, render and completion states in Projects and Dashboard.

---

## Features

### 1. Structured AI script generation

FastAPI sends the content request to the OpenAI Responses API and validates the
structured result with Pydantic.

The production blueprint includes:

- Title
- Hook
- Full narration
- Call to action
- Sequential scenes
- Visual direction
- Subtitle text
- Duration for every scene

The validated output becomes the source of truth for voice generation, scene
composition, subtitles and final rendering.

### 2. Authorized voice generation

Chatterbox Turbo performs zero-shot voice cloning from a private reference recording,
watermarks generated audio and exports normalized WAV narration.

Security expectations:

- Use only a voice you own or have permission to use.
- Private voice files are excluded from Git.
- Generated voice files are stored under the configured backend data directory.
- GPU deployments use `CHATTERBOX_DEVICE=cuda`.

### 3. AI-generated visual scenes

When no media is uploaded, the OpenAI Image API creates a text-free landscape image
for each scene. FFmpeg then turns that image into a moving video segment.

This prevents internal production prompts from appearing as text inside the final video.

### 4. Media upload and validation

The backend validates file size, extension, media streams and project-scoped paths for:

- Images
- Video clips
- Voice references
- Logos
- Background music

### 5. Animated image scenes

FFmpeg applies:

- Automatic motion
- Zoom in and zoom out
- Pan left, right, up and down
- Fade in and fade out
- Crossfade transitions
- Scale and crop normalization

### 6. Asynchronous voice and video jobs

Long-running voice and render requests return HTTP `202` with a job ID. The frontend
polls job status and displays:

```text
queued → processing → completed | failed
```

Job metadata is stored under `DATA_DIR`, so project status survives normal page refreshes.
Active in-process work does not resume automatically after a backend restart.

### 7. Video rendering pipeline

FFmpeg combines:

- Narration WAV
- Uploaded or generated scene media
- Motion and transitions
- SRT subtitles and optional burn-in
- Optional logo
- Optional background music

Outputs:

- 720p HD MP4
- 1080p Full HD MP4
- SRT subtitle file

### 8. Projects and Dashboard

Browser localStorage tracks safe project metadata and statuses:

- Draft
- Script Ready
- Voice Ready
- Rendering
- Completed
- Failed

---

## Architecture

![CreatorOps AI end-to-end architecture](docs/images/creatorops-ai-architecture.png)

### Application flow

```text
User idea
   ↓
Next.js Create workflow
   ↓
FastAPI API and job orchestration
   ↓
OpenAI Responses API
   ├── structured script
   └── timed scene plan
   ↓
Chatterbox Turbo authorized narration
   ↓
Uploaded media or OpenAI-generated scene visuals
   ↓
FFmpeg motion and rendering pipeline
   ↓
Transitions + subtitles + logo + music
   ↓
720p / 1080p MP4 + SRT
   ↓
Projects page and Dashboard
```

### Cloud demo architecture

```text
Browser
   ↓
Vercel-hosted Next.js frontend
   ↓ HTTPS API URL
FastAPI backend
   ├── OpenAI Responses API
   ├── OpenAI Image API
   ├── Chatterbox Turbo on NVIDIA CUDA
   ├── FFmpeg / FFprobe
   └── asynchronous job polling
   ↓
Configured DATA_DIR / persistent volume
   ├── voice references
   ├── uploads
   ├── model cache
   ├── job metadata
   └── WAV / MP4 / SRT outputs
```

---

## Tech stack

### Frontend

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- Browser localStorage
- Vercel

### Backend

- Python 3.10+
- FastAPI
- Pydantic
- Uvicorn
- python-dotenv
- python-multipart
- Persistent job metadata

### AI

- OpenAI Responses API
- OpenAI Structured Outputs
- OpenAI Image API
- GPT-5.6 for production planning
- `gpt-image-2` for scene visuals
- [Chatterbox Turbo](https://github.com/resemble-ai/chatterbox) 0.1.7
- Transformers

### Video and audio

- FFmpeg
- FFprobe
- Pillow
- H.264 / AAC
- SRT subtitles

### Infrastructure

- Docker / Docker Buildx
- Docker Hub image
- Vast.ai NVIDIA GPU backend
- Vercel frontend
- GitHub Actions

### Testing

- Pytest
- HTTPX
- Mocked OpenAI integrations
- Mocked Chatterbox Turbo integration
- Mocked FFmpeg integration
- Real FFmpeg smoke tests
- ESLint
- Next.js production build

---

## Deployment modes

### Mode A: Fully local

```text
Local Next.js frontend
→ Local FastAPI backend
→ OpenAI APIs
→ Chatterbox on CUDA, Apple MPS or CPU
→ Local FFmpeg rendering
```

This is the safest development and backup environment.

### Mode B: Local frontend with cloud GPU backend

```text
localhost:3000
→ Vast.ai FastAPI endpoint
→ NVIDIA GPU voice generation
→ Cloud FFmpeg rendering
```

Set:

```env
NEXT_PUBLIC_API_URL=http://PUBLIC_IP:EXTERNAL_PORT
```

This mode is useful for fast testing and demo recording.

### Mode C: Vercel frontend with HTTPS backend

```text
Vercel frontend
→ Stable HTTPS FastAPI backend
```

Set in Vercel:

```env
NEXT_PUBLIC_API_URL=https://your-fastapi-backend.example.com
```

Set in the backend:

```env
CORS_ORIGINS=https://creatorops-ai-one.vercel.app
```

A Vercel HTTPS page should not call a plain HTTP backend because browsers may block
mixed content. Use a stable HTTPS backend URL for a fully public deployment.

Deployment guides:

- [Vercel frontend deployment](docs/VERCEL_DEPLOYMENT.md)
- [Vast.ai GPU backend deployment](docs/VAST_DEPLOYMENT.md)

---

## How to run locally

### 1. Clone

```bash
git clone https://github.com/Bhaktabahadurthapa/creatorops-ai.git
cd creatorops-ai
```

### 2. Install FFmpeg

```bash
brew install ffmpeg
```

### 3. Configure and start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 4. Configure and start the frontend

Open another terminal:

```bash
cd creatorops-ai/frontend
npm install
cp .env.example .env.local
npm run dev
```

Open:

```text
http://localhost:3000
```

---

## Environment variables

### Backend: `backend/.env`

```env
OPENAI_API_KEY=your_real_openai_api_key
OPENAI_MODEL=gpt-5.6
OPENAI_IMAGE_MODEL=gpt-image-2

DATA_DIR=
VOICE_REFERENCE_PATH=private/my_voice.wav
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CHATTERBOX_DEVICE=auto
PORT=8000
HF_HOME=
XDG_CACHE_HOME=
```

For a Vast.ai GPU backend:

```env
OPENAI_API_KEY=configure_in_vast
OPENAI_MODEL=gpt-5.6
OPENAI_IMAGE_MODEL=gpt-image-2
DATA_DIR=/workspace/data
VOICE_REFERENCE_PATH=private/my_voice.wav
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CHATTERBOX_DEVICE=cuda
PORT=8000
HF_HOME=/workspace/data/models
XDG_CACHE_HOME=/workspace/data/cache
```

### Frontend: `frontend/.env.local`

Local backend:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Cloud GPU backend:

```env
NEXT_PUBLIC_API_URL=http://PUBLIC_IP:EXTERNAL_PORT
```

Production frontend:

```env
NEXT_PUBLIC_API_URL=https://your-fastapi-backend.example.com
```

### Security rules

- Never commit `.env` or `.env.local`.
- Never place `OPENAI_API_KEY` in frontend code.
- Never commit private voice recordings.
- Never commit uploaded media or generated WAV/MP4 files.
- Keep cloud templates private when they contain secrets.

---

## Voice-reference setup

### Upload through the application

1. Open `/create`.
2. Upload a 6–20 second reference recording.
3. Use one speaker in a quiet room.
4. Upload only a voice you own or are authorized to use.
5. Wait for the status to show ready.
6. Generate narration.

### Add a local WAV manually

```bash
mkdir -p backend/private
```

Place the file at:

```text
backend/private/my_voice.wav
```

Configure:

```env
VOICE_REFERENCE_PATH=private/my_voice.wav
```

`CHATTERBOX_DEVICE=auto` selects NVIDIA CUDA first, Apple MPS on compatible Macs,
and CPU as a fallback. Vast.ai deployments should use `CHATTERBOX_DEVICE=cuda`.
The first generation downloads and loads model assets; later requests reuse the cache.

---

## Testing

### Backend

```bash
cd backend
source .venv/bin/activate
pytest -v
```

### Frontend

```bash
cd frontend
npm run lint
npm run build
```

### Manual end-to-end validation

1. Enter a short content idea.
2. Generate the structured script.
3. Upload an authorized voice reference.
4. Generate narration and observe job polling.
5. Upload media or generate AI visual scenes.
6. Assign a source to every scene.
7. Enable subtitles.
8. Render a 720p preview.
9. Play and download the MP4.
10. Download the SRT file.

---

## Screenshots and build proof

Selected proof from the OpenAI, voice and rendering implementation workflow:

| OpenAI script integration | API contract and security validation |
| --- | --- |
| [![OpenAI Responses API implementation](docs/images/screenshots/openai-script-integration.png)](docs/images/screenshots/openai-script-integration.png) | [![API validation](docs/images/screenshots/api-security-validation.png)](docs/images/screenshots/api-security-validation.png) |

| Authorized voice integration | Video renderer implementation |
| --- | --- |
| [![Authorized voice integration](docs/images/screenshots/authorized-voice-integration.png)](docs/images/screenshots/authorized-voice-integration.png) | [![FFmpeg renderer](docs/images/screenshots/video-renderer-implementation.png)](docs/images/screenshots/video-renderer-implementation.png) |

| Video rendering validation | Final project audit |
| --- | --- |
| [![Rendering validation](docs/images/screenshots/video-renderer-validation.png)](docs/images/screenshots/video-renderer-validation.png) | [![Final audit](docs/images/screenshots/final-project-audit.png)](docs/images/screenshots/final-project-audit.png) |

The complete user-facing workflow is shown in the [demo video](https://youtu.be/cPOUEL0nrMI).

---

## OpenAI Build Week

CreatorOps AI was substantially developed during OpenAI Build Week.

### How GPT-5.6 is used

GPT-5.6 generates the validated production blueprint that drives narration, scene
composition, subtitle timing and rendering.

### How Codex was used

Codex helped to:

- Build and connect Next.js and FastAPI.
- Integrate structured OpenAI responses.
- Integrate AI-generated scene visuals.
- Adapt the authorized Chatterbox Turbo voice service.
- Improve the FFmpeg rendering pipeline.
- Add secure uploads and path validation.
- Add asynchronous jobs and frontend polling.
- Package the backend for NVIDIA GPU deployment.
- Add tests, deployment guides and repository documentation.
- Diagnose local and cloud deployment issues.

### Build evidence

- Dated Git commits
- Pull requests for voice, video and deployment integrations
- [`docs/BUILD_WEEK_CHANGELOG.md`](docs/BUILD_WEEK_CHANGELOG.md)
- Automated tests and real rendering validation
- Public [demo video](https://youtu.be/cPOUEL0nrMI)

---

## Known limitations

- Chatterbox Turbo and video rendering are compute- and memory-intensive.
- The first voice generation has model download and loading latency.
- Voice and video jobs run in-process; a backend restart interrupts active work.
- Job metadata persists, but interrupted jobs do not automatically resume.
- Project metadata is stored in browser localStorage rather than a database.
- Generated files do not yet have automatic expiration or cleanup.
- AI visual generation uses paid OpenAI API credits and adds scene-generation time.
- Subtitle burn-in depends on the installed FFmpeg build.
- The current public frontend requires a reachable backend to generate content.
- Temporary Vast.ai instances use temporary storage unless persistent storage is attached.
- Authentication, rate limiting and multi-user isolation are not yet implemented.

---

## Roadmap

### Completed MVP and submission work

- [x] Next.js frontend
- [x] FastAPI backend
- [x] GPT-5.6 structured script generation
- [x] Timed scene planning
- [x] Authorized Chatterbox Turbo narration
- [x] Media upload and validation
- [x] AI-generated visual scenes
- [x] Animated image motion
- [x] Subtitles and SRT generation
- [x] Logo and background music
- [x] 720p and 1080p MP4 export
- [x] Projects page and Dashboard
- [x] Asynchronous job polling
- [x] Docker GPU packaging
- [x] Vast.ai deployment guide
- [x] Vercel deployment and GitHub Action
- [x] Architecture and build-proof images
- [x] Demo video
- [x] Automated tests

### Next production milestones

- [ ] Stable HTTPS GPU backend
- [ ] Redis-backed distributed job queue
- [ ] Automatic file cleanup
- [ ] Structured logging and monitoring
- [ ] Rate limiting and API authentication
- [ ] Object storage for media and outputs
- [ ] PostgreSQL or Supabase project persistence
- [ ] User authentication and isolation
- [ ] Reusable brand kits and multiple authorized voices
- [ ] Platform-specific export and publishing presets

---

## Previous work reused

CreatorOps AI integrates and extends reusable service logic from two earlier prototypes:

- **Text-to-Own_Voice-Apps:** authorized custom-voice generation
- **my_project:** local audio, image, video and FFmpeg production workflow

The original projects remain separate. CreatorOps AI adds the integrated Next.js/FastAPI
workflow, structured OpenAI planning, AI scene generation, async jobs, cloud packaging,
testing and complete production orchestration.

---

## Responsible use

- Use only voices you own or have explicit permission to use.
- Do not use generated audio to impersonate or deceive others.
- Review generated scripts, visuals, narration and subtitles before publishing.
- Protect API keys, voice references, uploads and generated outputs.
- Retain required third-party notices when redistributing dependencies.

---

## Author

**Bhakta Bahadur Thapa**

CreatorOps AI was designed and built as an end-to-end applied AI video-production system
for OpenAI Build Week 2026.
