# Video Engine (Phase 3-5)

Python backend that renders faceless short videos and publishes them.

## Pipeline

1. **Groq** — generates a ~30s script (Llama 3) from the `topic`.
2. **edge-tts** — converts the script to an MP3 (free, no external API).
3. **Pexels** — fetches 3 vertical stock videos matching the topic.
4. **MoviePy** — cover-crops to 1080x1920, adds audio, overlays captions, exports MP4.
5. **Firebase Storage** — uploads the MP4; **Firestore** status → `completed`.
6. **Publish** — YouTube / Instagram / TikTok (Phase 4-5); status → `posted`.

## File layout

```
backend/
├── generate.py          # CLI entry point + flow orchestration
├── config.py            # env-based config
├── script_gen.py        # Groq script generation
├── tts.py               # edge-tts
├── assets.py            # Pexels fetch/download
├── assemble.py          # MoviePy assembly + captions
├── firebase_store.py    # Storage upload + Firestore updates
├── publish.py           # YouTube / Instagram / TikTok publishers
└── requirements.txt
```

## Run locally

```bash
cd backend
pip install -r requirements.txt
# Install ffmpeg on your machine (MoviePy requires it):
#   apt install ffmpeg   (Linux)
#   brew install ffmpeg  (macOS)
#   winget install ffmpeg (Windows)

# Create a .env from the values below, then:
python generate.py --userId "<uid>" --topic "Deep sea facts" --platform youtube_shorts --documentId "<docId>"
```

## Environment variables / repo secrets

| Variable | Phase | Required | Description |
| -------- | ----- | -------- | ----------- |
| `GROQ_API_KEY` | 3 | yes | Groq API key (console.groq.com) |
| `PEXELS_API_KEY` | 3 | yes | Pexels API key (www.pexels.com/api) |
| `FIREBASE_CREDENTIALS` | 3 | yes | Firebase service-account JSON (path or raw JSON) |
| `FIREBASE_STORAGE_BUCKET` | 3 | yes | Firestore/Storage bucket id, e.g. `app.appspot.com` |
| `GOOGLE_CLIENT_SECRETS` | 4 | for YouTube | Path to the OAuth `client_secret_*.json` |
| `GOOGLE_TOKEN` | 4 | for YouTube | Path to the stored OAuth token JSON |
| `INSTAGRAM_ACCESS_TOKEN` | 4 | for Instagram | Meta Graph API long-lived token |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | 4 | for Instagram | Instagram Professional account id |
| `TIKTOK_ACCESS_TOKEN` | 5 | for TikTok | 24h user access token (captured via frontend OAuth) |

Add these to GitHub: **Settings → Secrets and variables → Actions → New repository secret**.

---

## Phase 4a — YouTube Shorts: Google Cloud Console setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create/select a project.
2. Search for and enable **YouTube Data API v3**.
3. **OAuth consent screen** → External → add a test user (your Google account).
   - Add scope: `https://www.googleapis.com/auth/youtube.upload`.
4. **Credentials → Create credentials → OAuth client ID → Web application**.
   - Authorized redirect URIs: `http://localhost` (for local testing).
   - Download the `client_secret_*.json` and save it.
5. Run the local helper to get a token file (this one-time step yields the
   refresh token used by the runner):

```bash
cd backend
python -m client_oauth
```

This opens a browser, you authorize, and it writes the token JSON. Set
`GOOGLE_TOKEN` to the path of that file.

> Because this is an OAuth **user** token and stored in the repo (as a secret),
> the video uploads to **your** channel.

## Phase 4b — Instagram Reels: Meta Developer Portal setup

1. [Meta for Developers](https://developers.facebook.com/) → Create app
   (**Business** type) → add the **Instagram Graph API** product.
2. Link an **Instagram Professional account** to the app.
3. App **Settings → Basic**: copy the **App ID** and **App Secret**.
4. **Tools → Graph API Explorer**:
   - Select your app → add a token with scopes:
     `instagram_basic`, `instagram_content_publish`, `pages_show_list`.
   - Generate a **long-lived** token (exchange the short-lived one via
     `access_token` + `grant_type=ig_exchange_token`).
5. Get your `INSTAGRAM_BUSINESS_ACCOUNT_ID` via
   `GET /me/accounts` (Facebook page) then
   `GET /{page-id}?fields=instagram_business_account`.
6. Put the long-lived token and the business account id in repo secrets.

> Video must be already public on the internet, so it is uploaded to Firebase
> Storage first (Phase 3) and the public URL is passed to Instagram.

## Phase 5 — TikTok: Developer Portal + OAuth

1. [TikTok for Developers](https://developers.tiktok.com/) → create an app.
   - Add the scopes: **Video publish** (`video.publish`), **Basic info**
     (`user.info.basic`).
   - Register the **redirect URI**:
     `https://<your-site>/#/tiktok/callback` — must match exactly.
2. In the Cloudflare Worker config (non-secret vars):
   - `TIKTOK_REDIRECT_URI` = the exact redirect URI above.
3. Add Worker secrets:
   - `TIKTOK_CLIENT_KEY` (the app's **Client Key** = `client_key`).
   - `TIKTOK_CLIENT_SECRET` (the app's **Client Secret**).
4. Add to your frontend `.env`:
   - `VITE_TIKTOK_CLIENT_KEY`
   - `VITE_TIKTOK_REDIRECT_URI`

Flow:
- The "Connect TikTok" button redirects to TikTok OAuth.
- TikTok redirects back to `/#/tiktok/callback?code=...&state=<userId>`.
- The frontend posts `{ userId, code }` to the Worker `/api/tiktok/token`,
  which exchanges the code for an access token (secret stays server-side)
  and stores it in the `tiktok_tokens` collection.
- `publish.tiktok_publish()` reads `TIKTOK_ACCESS_TOKEN` (set as a repo secret
  from that stored token) and publishes via the Content Posting API.

> TikTok user access tokens last **24 hours**. For an unaudited app, publish
> with `privacy_level = "SELF_ONLY"` and set it to `PUBLIC_TO_EVERYONE` once
> the app is approved.

---

## GitHub Actions

The workflow `.github/workflows/video_builder.yml` runs on
`repository_dispatch` with `types: [generate-video]` and passes
`client_payload` to `generate.py`.
