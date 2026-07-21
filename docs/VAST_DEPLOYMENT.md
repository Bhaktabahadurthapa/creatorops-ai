# Deploying the CreatorOps AI backend on Vast.ai

The production layout keeps the Next.js frontend on Vercel and runs FastAPI,
Chatterbox Turbo, HyperFrames, Chromium, and FFmpeg in one GPU instance. The
backend returns job IDs immediately for voice and video work so the browser can
poll without holding a long rendering request open.

## Build the backend image

From the repository root, build an AMD64 image for Vast.ai:

```bash
docker buildx build \
  --platform linux/amd64 \
  --file Dockerfile.backend \
  --tag lishan2023/creatorops-ai-backend:deploy-production \
  --push \
  .
```

Authenticate to Docker Hub before pushing. Do not place a registry token,
OpenAI key, or private voice recording in the image.

The GitHub Actions workflow publishes this image to Docker Hub. Configure these
repository settings before running it:

- Variable `DOCKERHUB_USERNAME`: `lishan2023`
- Secret `DOCKERHUB_TOKEN`: a Docker Hub personal access token with permission
  to push this repository

## Configure the instance

Create a Vast.ai GPU instance from
`lishan2023/creatorops-ai-backend:latest`, then configure:

- Exposed HTTP port: `8000`
- Docker port option: `-p 8000:8000`
- Volume mount path: `/workspace`
- Persistent data directory: `/workspace/data`
- Container command: use the image default (`backend/start.sh`)
- One running API process per instance

Vast.ai maps container port `8000` to a random public host port. Open **IP Port
Info** on the instance card to find a mapping such as:

```text
70.54.34.6:35496 -> 8000/tcp
```

The direct API URL in that example is `http://70.54.34.6:35496`. A Vercel
frontend requires an HTTPS endpoint; use a stable Cloudflare Tunnel or another
TLS reverse proxy and point it at the mapped Vast.ai address.

Files written outside `/workspace` can be lost when an instance is reset. The
application therefore keeps model downloads, uploads, private references, job
metadata, WAV files, MP4 files, and SRT files below `/workspace/data`.

## Configure environment variables

Use `backend/vast.env.example` as the non-secret checklist. Configure the real
values in Vast.ai:

```env
OPENAI_API_KEY=configure_as_a_vast_secret
OPENAI_MODEL=gpt-5.6
OPENAI_IMAGE_MODEL=gpt-image-2
DATA_DIR=/workspace/data
VOICE_REFERENCE_PATH=private/my_voice.wav
CORS_ORIGINS=https://creatorops-ai-one.vercel.app
CHATTERBOX_DEVICE=cuda
PORT=8000
HF_HOME=/workspace/data/models
XDG_CACHE_HOME=/workspace/data/cache
```

`CORS_ORIGINS` accepts a comma-separated list when both a production domain and
Vercel preview domain are needed. Never use `*` with private voice uploads.

## Verify the backend

After the instance starts, replace the example address with the mapped public
IP and port:

```bash
curl http://PUBLIC_IP:EXTERNAL_PORT/health
curl http://PUBLIC_IP:EXTERNAL_PORT/ready
```

`/health` confirms the API process is alive. `/ready` checks persistent storage,
FFmpeg, FFprobe, HyperFrames, and Chromium without loading Chatterbox Turbo.
The first real voice job downloads and loads Chatterbox Turbo into GPU memory,
so that request has a cold start.

Voice and video endpoints return HTTP `202`:

```json
{
  "job_id": "...",
  "job_type": "voice",
  "status": "queued",
  "status_url": "/api/jobs/..."
}
```

Poll the returned status URL until it reports `completed` or `failed`.

## Connect Vercel

Create a stable HTTPS address for the Vast.ai API, then set this Vercel
Production environment variable and redeploy the frontend:

```env
NEXT_PUBLIC_API_URL=https://your-fastapi-backend.example.com
```

Replace the example FastAPI hostname with the real stable HTTPS backend address.
Set the instance's production origin to:

```env
CORS_ORIGINS=https://creatorops-ai-one.vercel.app
```

## Current production limits

- Job metadata survives on the persistent volume, but an in-progress task does
  not automatically resume after an instance restart.
- A single process serializes GPU voice and video jobs to reduce GPU-memory
  contention.
- Generated media is local to the attached volume and needs a backup or object
  storage strategy for long-term retention.
- The API has no authentication or rate limiting. Do not expose private voice
  cloning to untrusted public users until those controls exist.

Vast.ai documents random external port mappings in its
[networking guide](https://docs.vast.ai/guides/instances/connect/networking)
and HTTPS tunnel options in its
[Instance Portal guide](https://docs.vast.ai/guides/instances/connect/instance-portal).
