# Project Context — Faceless Video Studio

Authoritative context for the automated faceless short-video generator. Read
this to understand the architecture, key decisions, and current state before
making changes.

Last updated: 2026-08-27 · Repo: `https://github.com/leoblixt25/Faceless_auto` (branch `main`)

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
│ TikTok OAuth       │            │  • GitHub dispatch│           │  Pexels → MoviePy │   └─────────────────┘
└────────────────────┘            └──────────────────┘           │  → Firebase       │
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
5. Engine renders the video, uploads to Firebase Storage, sets
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
| `README.md` | Root overview + per-phase pointers |
| `PROJECT_CONTEXT.md` | This file |

## Data model — Firestore `videos` collection

| Field | Type | Notes |
| ----- | ---- | ----- |
| `userId` | string | requesting user's UID |
| `topic` | string | prompt / topic |
| `platform` | string | `youtube_shorts` \| `tiktok` \| `instagram_reels` |
| `status` | string | `pending` → `processing` → `completed` → `posted` (or `failed`) |
| `createdAt` | server timestamp | set at creation |
| `updatedAt` | server timestamp | status transitions |
| `videoUrl` | string | Firebase Storage public URL (set on `completed`) |
| `socialLink` | string | live platform link (set on `posted`) |

Separate collections: `tiktok_tokens` (per-user TikTok access token).

## Key design decisions & why

- **Firebase Admin SDK does NOT run in Cloudflare Workers.** The Worker mints a
  short-lived OAuth2 access token from the service account (RS256 JWT via
  WebCrypto) and talks to Firestore over its REST API (`worker/src/firebase.ts`).
  The full Admin SDK *is* used on the GitHub runner (`backend/firebase_store.py`)
  where Node APIs are available.
- **Bridge pattern.** The frontend never talks to GitHub directly; the Worker
  is the only thing with `GITHUB_PAT`, keeping the token server-side.
- **Server-side OAuth for TikTok.** The TikTok client secret stays in the
  Worker; the frontend sends `{ userId, code }` and the Worker exchanges it
  and persists the token.
- **HashRouter** on the frontend (works on any static host without server
  rewrites). TikTok redirect URI is therefore
  `<site-url>/#/tiktok/callback?code=...&state=<userId>`.
- **TikTok token is 24h**; publish uses `SELF_ONLY` privacy until the app is
  audited/approved, then switch to `PUBLIC_TO_EVERYONE`.
- **YouTube Shorts** need no explicit flag; YouTube infers "Short" from
  <60s vertical video. Uploads use OAuth user token (owner's channel),
  category 22.
- **Instagram** uses the two-step `media` → `media_publish` Graph API flow and
  requires a publicly reachable video URL (hence Firebase Storage first).

## Environment variables / secrets

Frontend (`.env`):
`VITE_FIREBASE_*`, `VITE_WORKER_URL`, `VITE_TIKTOK_CLIENT_KEY`,
`VITE_TIKTOK_REDIRECT_URI`.

Worker (secret + non-secret `wrangler.toml`):
`GITHUB_PAT`, `FIREBASE_CREDENTIALS` (secrets); `ALLOWED_ORIGIN`, `GITHUB_REPO`,
`SKIP_FIRESTORE`, `TIKTOK_REDIRECT_URI` (vars);
`TIKTOK_CLIENT_KEY`/`TIKTOK_CLIENT_SECRET` (secrets).

GitHub Actions repo secrets (backend):
`GROQ_API_KEY`, `PEXELS_API_KEY`, `FIREBASE_CREDENTIALS`,
`FIREBASE_STORAGE_BUCKET`; for publishing `GOOGLE_CLIENT_SECRETS`,
`GOOGLE_TOKEN`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`,
`TIKTOK_ACCESS_TOKEN`.

## Useful commands

```bash
# Frontend
npm install
npm run dev
npm run build && npm run lint

# Worker
cd worker
npm install
npm run typecheck
npx wrangler deploy --dry-run
npx wrangler secret put GITHUB_PAT          # then FIREBASE_CREDENTIALS, ...
npm run deploy

# Backend (local syntax check only; heavy deps installed by CI)
cd backend
python -m py_compile generate.py
```

## Current status

- Phase 1 (frontend + auth + DB): done
- Phase 2 (Cloudflare Worker bridge): done
- Phase 3 (video engine): done
- Phase 4 (YouTube + Instagram publish): done
- Phase 5 (TikTok publish + OAuth): done

## Known limitations / next steps

- TikTok token must be refreshed beyond 24h (refresh-token flow not yet wired
  into publishing).
- `updatedAt` on transitions and real-time feed rely on Firestore security rules
  being configured correctly (rules are documented in `README.md`).
- Video pipeline is untested against live APIs (Groq / Pexels / MoviePy) outside
  CI; add integration tests or a manual smoke run before trusting the engine.
- The Worker `findPendingVideo` matches by `userId` + `status == pending`;
  ensure the frontend passes the correct `documentId` so the right doc updates.
