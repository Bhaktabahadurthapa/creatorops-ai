# Deploying CreatorOps AI with Vercel

This guide deploys the CreatorOps AI **Next.js frontend** to Vercel through
GitHub Actions.

## Deployment architecture

```text
Browser
  ↓
Next.js frontend on Vercel
  ↓ NEXT_PUBLIC_API_URL
Public FastAPI backend on a separate host
  ↓
OpenAI + XTTS + FFmpeg + local or persistent media storage
```

The current backend cannot run as part of this Vercel frontend deployment. It
loads a voice model, invokes FFmpeg, and writes uploaded and generated files to
disk. Deploy it to a persistent Python-capable host before enabling the Vercel
workflow.

## What you need to provide

### Vercel project configuration

- A Vercel project connected to this repository.
- Project root directory: `frontend`.
- Framework preset: Next.js.
- Production branch: `main`.
- Any `frontend/vercel.json` or `frontend/vercel.ts` configuration you want to
  use. Only one of those files can exist.
- An optional custom production domain.

### Public backend configuration

- The HTTPS URL of the deployed FastAPI backend, for example
  `https://api.example.com`.
- Backend CORS configuration that allows the Vercel production domain and any
  preview domains you intend to use.
- Persistent storage or a cleanup strategy for uploads, generated WAV files,
  MP4 files, and subtitles.

Do not use `http://127.0.0.1:8000` in production. That address refers to the
visitor's own computer when used by a deployed frontend.

## Configure Vercel

In the Vercel project, open **Settings → Environment Variables** and add:

```env
NEXT_PUBLIC_API_URL=https://your-public-backend.example.com
```

Add it to the Production environment. Add it to Preview as well if preview
deployments will be enabled later. Redeploy after changing a Vercel environment
variable because existing deployments do not receive updates automatically.

## Configure GitHub Actions

Open the GitHub repository and go to **Settings → Secrets and variables →
Actions**.

Add these repository secrets:

| Secret | Purpose |
| --- | --- |
| `VERCEL_TOKEN` | Authorizes the Vercel CLI. Create it in Vercel account settings. |
| `VERCEL_ORG_ID` | Identifies the Vercel user or team that owns the project. |
| `VERCEL_PROJECT_ID` | Identifies the Vercel frontend project. |

Never paste `VERCEL_TOKEN` into chat, source code, a configuration file, an
issue, or a pull request.

To retrieve the organization and project IDs safely:

```bash
cd creatorops-ai
vercel link --repo
```

The link command creates local `.vercel` configuration. That directory is
ignored by Git and must not be committed.

After all three secrets are configured, add this repository variable:

```text
VERCEL_DEPLOY_ENABLED=true
```

The variable is an intentional safety switch. Until it is set to `true`, the
deployment job is skipped instead of failing because configuration is missing.

## Run the deployment

The workflow is defined in
`.github/workflows/vercel-production.yml`.

It runs when:

- A frontend-related change is pushed to `main`.
- It is started manually from **GitHub → Actions → Deploy frontend to Vercel →
  Run workflow**.

The workflow:

1. Installs frontend dependencies.
2. Runs frontend lint.
3. Pulls the Vercel production settings and environment variables.
4. Builds Vercel artifacts.
5. Deploys the prebuilt artifacts to production.
6. Writes the production URL to the GitHub Actions job summary.

## Avoid duplicate deployments

Vercel's native Git integration can deploy every push automatically. If this
GitHub Action is the deployment authority, disable the duplicate automatic Git
deployment for the Vercel project. Otherwise a single push may create two
deployments.

## Files or values to send for review

You can provide these non-secret items for repository review:

- `frontend/vercel.json` or `frontend/vercel.ts`.
- The intended public backend URL.
- The intended Vercel project name and custom domain.
- Any build-command or Node.js-version requirements.

Do **not** send the Vercel token, OpenAI key, private voice reference, project
uploads, or generated media. Configure secrets directly in GitHub or Vercel.
