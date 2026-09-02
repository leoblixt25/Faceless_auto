# Project Context — Faceless Video Studio

Authoritative context for the automated faceless short-video generator. Read
this to understand the architecture, key decisions, and current state before
making changes.

Last updated: 2026-09-02 · Repo: `https://github.com/leoblixt25/Faceless_auto` (branch `main`)

## What this is

A free-tier, fully automated pipeline that turns a text prompt into a finished
vertical short video and publishes it to YouTube Shorts, Instagram Reels, and
TikTok. There is no human in the loop after submission.

## High-level architecture

```
React (Vite + Tailwind)          Cloudflare Worker             GitHub Actions            Social platforms
┌────────────────────┐   POST     ┌──────────────────┐  dispatch ┌──────────────────┐  ┌─────────────────┐
│ Google Sign-in     │ ─────────► │ /api/generate    │ ─────────► │ video_builder.yml │  │ YouTube Shorts  │
│ New Video form     │            │ (Hono)           │           │  generate.py      ├──►│ Instagram Reels │
│ Video feed (realtime)│          │  • Firestore     │           │  Groq → TTS →     │   │ TikTok          │
│ TikTok OAuth       │            │  • GitHub dispatch│           │  AI/Pexels →      │   └─────────────────┘
└────────────────────┘            └──────────────────┘           │  MoviePy → Firebase│
                                                                 └──────────────────┘
```

Data flow (owned by `documentId` in Firestore):

1. User logs in with Google and submits the "New Video" form.
2. Frontend writes a `videos/{docId}` doc (`status: pending`) and POSTs
   `{ userId, topic, platform, documentId }` to `VITE_WORKER_URL/api/generate`.
3. Worker finds the pending doc, sets `status: processing`, and dispatches
   GitHub `repository_dispatch` with `event_type: generate-video` and the
   payload (now includes `documentId`).
4. GitHub Actions runs `backend/generate.py` with the payload.
5. Engine renders the video, uploads to GitHub Releases, sets
   `status: completed` + `videoUrl`.
6. Engine publishes to the target platform and sets `status: posted` +
   `socialLink`.

## Repository layout

| Path | Contents |
| ---- | -------- |
| `src/` | React frontend (Phases 1, 5 TikTok OAuth) |
| `worker/` | Cloudflare Worker API bridge (Phase 2) |
| `backend/` | Python video engine + publishers (Phases 3–5) |
| `.github/workflows/` | CI/CD workflows |
| `scripts/deploy.mjs` | Robust deploy script (build + deploy + re-apply secrets) |
| `README.md` | Root overview + per-phase pointers |
| `PROJECT_CONTEXT.md` | This file |

## Video engine — multi-backend AI pipeline

The engine (`backend/generate.py`) tries video backends in priority order.
If one fails (e.g. out of credits), the next is tried so videos always complete.

| Priority | Engine | Module | Model | Quality | Notes |
|----------|--------|--------|-------|---------|-------|
| 1 | **Replicate** | `replicate.py` | `kwaivgi/kling-v3-omni-video` | Cinematic | Multi-shot (up to 6 scenes × 15s = 90s). Best quality. Requires paid credits. |
| 2 | **Magic Hour** | `magichour.py` | `ltx-2.3` / `wan-2.2` | Low | Free tier only. LTX 2.3 = 24 cr/s. |
| 3 | **Seedance** | `seedance.py` | `seedance-2.0` | Medium | Requires paid credits. |
| 4 | **Pexels** | `assemble.py` | Stock footage | Stock | Always available fallback. |

**Engine chain**: Replicate → Magic Hour → Seedance → Pexels

### Scene generation

1. `script_gen.py` `generate_script()` — Groq writes a spoken narration script
2. `script_gen.py` `generate_scenes()` — Groq splits script into N visual scene prompts
   - Each prompt: specific subject, natural action, camera movement, lighting, mood, photorealistic style
   - Prompts must be visually distinct from each other
3. Engine renders each scene prompt into a video clip
4. `assemble_seedance.py` concatenates clips + TTS narration + captions → final MP4

### Caption rendering

- Font size: 42px (white with black stroke)
- Caption width: 840px (leaves 120px margin on each side)
- Height cap: 250px (prevents vertical overflow)
- Position: centered at y=81% from top
- Chunks: 4 words or 36 chars max per caption

## Environment variables / secrets

Frontend (`.env`):
`VITE_FIREBASE_*`, `VITE_WORKER_URL`, `VITE_TIKTOK_CLIENT_KEY`,
`VITE_TIKTOK_REDIRECT_URI`.

Worker (secret + non-secret `wrangler.toml`):
`GITHUB_PAT`, `GH_PAT`, `FIREBASE_CREDENTIALS`, `SEEDANCE_API_KEY`,
`MAGIC_HOUR_API_KEY`, `REPLICATE_API_TOKEN` (secrets);
`ALLOWED_ORIGIN`, `GITHUB_REPO`, `SKIP_FIRESTORE`, `TIKTOK_REDIRECT_URI` (vars);
`TIKTOK_CLIENT_KEY`/`TIKTOK_CLIENT_SECRET` (secrets).

GitHub Actions repo secrets (backend):
`GROQ_API_KEY`, `PEXELS_API_KEY`, `FIREBASE_CREDENTIALS`,
`FIREBASE_STORAGE_BUCKET`, `SEEDANCE_API_KEY`, `MAGIC_HOUR_API_KEY`,
`REPLICATE_API_TOKEN`; for publishing `GOOGLE_CLIENT_SECRETS`,
`GOOGLE_TOKEN`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`,
`TIKTOK_ACCESS_TOKEN`.

## Secrets management

**Every `wrangler deploy` wipes worker secrets.** The deploy script
(`scripts/deploy.mjs`) automatically re-applies them from `worker/.env.secrets`
after each deploy.

The `worker/.env.secrets` file is gitignored and contains `KEY=VALUE` pairs,
one per line. It must be kept in sync with the Cloudflare worker secrets.

To manually set a secret:
```bash
cd worker
echo "SECRET_NAME=value" | npx wrangler secret put SECRET_NAME
```

## Useful commands

```bash
# Frontend
npm install
npm run dev
npm run build && npm run lint

# Full deploy (builds frontend + deploys worker + re-applies secrets)
npm run deploy

# Worker (manual)
cd worker
npm install
npm run typecheck
npx wrangler deploy --dry-run

# Backend (local syntax check only; heavy deps installed by CI)
cd backend
python -m py_compile generate.py
python -m py_compile replicate.py
python -m py_compile magichour.py
python -m py_compile seedance.py
python -m py_compile assemble_seedance.py
```

## Current status

- Phase 1 (frontend + auth + DB): done
- Phase 2 (Cloudflare Worker bridge): done
- Phase 3 (video engine — multi-backend): done
- Phase 4 (YouTube + Instagram publish): done
- Phase 5 (TikTok publish + OAuth): done
- Caption rendering: fixed (v2 — no more text cutoff)
- Scene prompts: improved (cinematic photorealistic descriptions)

## Known limitations / next steps

- **Cinematic quality requires paid credits** on Replicate (Kling v3 Omni) or
  another provider. Free tiers cap at low-quality models.
- TikTok token must be refreshed beyond 24h (refresh-token flow not yet wired
  into publishing).
- `updatedAt` on transitions and real-time feed rely on Firestore security rules
  being configured correctly (rules are documented in `README.md`).
- The Worker `findPendingVideo` matches by `userId` + `status == pending`;
  ensure the frontend passes the correct `documentId` so the right doc updates.
- **Mystery deploy source**: unknown process deploys broken `index-*.js` bundles
  2–3 min after pushes, causing blank pages. Not yet resolved.
- Exposed API keys in chat history should be rotated after testing.
