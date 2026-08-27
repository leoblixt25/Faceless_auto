# Faceless Worker

A Cloudflare Worker that acts as a secure API bridge between the React frontend
and the GitHub Actions backend. It validates a generate request, marks the
matching Firestore document as `processing`, and dispatches a GitHub
`repository_dispatch` event to kick off the video-generation workflow.

Uses **Hono** on **Cloudflare Workers**.

> The Firebase Admin SDK cannot run in the Workers runtime, so this worker
> mints a short-lived OAuth2 access token from a service-account credential and
> talks to Firestore over its REST API.

## Endpoints

### `POST /api/generate`

Body:

```json
{
  "userId": "abc123",
  "topic": "Top 5 surprising facts about deep sea creatures",
  "platform": "youtube_shorts"
}
```

`platform` must be one of `youtube_shorts`, `tiktok`, `instagram_reels`.

Behavior:

1. Finds the user's most recent **pending** Firestore document in `videos`
   and updates its `status` to `processing`.
2. Dispatches a GitHub `repository_dispatch` event with
   `event_type: "generate-video"` and `client_payload: { userId, topic, platform }`.

Returns `202` when accepted, `400` for validation errors, and `502` if one of
the steps failed.

### `GET /`

Health check.

## Environment / Secrets

| Name                    | Type                  | Description                                                        |
| ----------------------- | --------------------- | ------------------------------------------------------------------ |
| `ALLOWED_ORIGIN`        | Environment variable  | Comma-separated list of allowed CORS origins (default: localhost)  |
| `GITHUB_REPO`           | Environment variable  | `owner/repo` to dispatch the workflow to                           |
| `SKIP_FIRESTORE`        | Environment variable  | Set to `"true"` to skip the Firestore status update (for testing)  |
| `GITHUB_PAT`            | **Secret**            | GitHub Personal Access Token with `repo` scope                     |
| `FIREBASE_CREDENTIALS`  | **Secret**            | Full service-account JSON as a string (see Firebase console)       |

## Local development

```bash
npm install
npx wrangler secret put GITHUB_PAT
npx wrangler secret put FIREBASE_CREDENTIALS
npm run dev
```

You can also create a `.dev.vars` file for local secrets (ignored by git):

```
GITHUB_PAT=ghp_xxx
FIREBASE_CREDENTIALS={"type":"service_account",...}
```

## Deploy

```bash
npm run deploy        # or: npx wrangler deploy
```

Wrangler reads `wrangler.toml` for the non-secret env vars. The two secrets
(`GITHUB_PAT`, `FIREBASE_CREDENTIALS`) are **not** stored in `wrangler.toml` and
must be added with:

```bash
npx wrangler secret put GITHUB_PAT
npx wrangler secret put FIREBASE_CREDENTIALS
```

> Secrets are stored encrypted and only injected into the Worker at runtime.

## Adding the secrets

### 1. `GITHUB_PAT`

Create a Personal Access Token (classic) with the **`repo`** scope:
GitHub → Settings → Developer settings → Personal access tokens → Generate
new token. Then:

```bash
npx wrangler secret put GITHUB_PAT
```

Paste the token when prompted.

### 2. `FIREBASE_CREDENTIALS`

Generate a service-account private key:
Firebase Console → Project settings → Service accounts → Generate new private
key. This downloads a JSON file. Paste its **entire JSON string** (single line
is fine):

```bash
npx wrangler secret put FIREBASE_CREDENTIALS
```

Paste the JSON when prompted (you may need `Set-Content` or a clipboard paste
if the value is long).
