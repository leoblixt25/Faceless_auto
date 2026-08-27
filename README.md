# Faceless Video Studio

A free-tier, automated faceless short video generator.

## Architecture

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

## Phases

- **Phase 1 — Frontend + Auth + DB:** React/Vite + Tailwind, Google Sign-In,
  Firestore `videos` schema, dashboard, real-time feed.
- **Phase 2 — API bridge:** Cloudflare Worker (Hono) — validates requests,
  marks Firestore `processing`, dispatches GitHub `repository_dispatch`.
- **Phase 3 — Video engine:** Python — Groq script → edge-tts → Pexels stock →
  MoviePy assembly → Firebase Storage → Firestore `completed`.
- **Phase 4 — Publish:** YouTube Shorts (Data API) and Instagram Reels
  (Graph API) uploading → Firestore `posted`.
- **Phase 5 — TikTok:** Content Posting API + "Login with TikTok" OAuth flow.

## Tech Stack

- **Frontend:** React 19 (Vite 8), Tailwind CSS v4, React Router v7 (HashRouter)
- **Auth & DB:** Firebase (Auth, Firestore, Storage)
- **Bridge:** Cloudflare Workers (Hono), GitHub REST API
- **Engine:** Python 3, Groq, edge-tts, Pexels, MoviePy, Firebase Admin
- **CI:** GitHub Actions

See the per-directory READMEs for detailed setup: `backend/README.md`,
`worker/README.md`, and the sections below for frontend setup.


## Getting Started

### 1. Install dependencies

```bash
npm install
```

### 2. Firebase setup

1. Go to the [Firebase Console](https://console.firebase.google.com/) and create a new project (or use an existing one).
2. In **Project Settings → General → Your apps**, click the **Web** icon (`</>`) to register a new web app.
3. Copy the Firebase config object values.
4. Create a `.env` file from the template and fill in the values:

```bash
cp .env.example .env
```

```env
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_STORAGE_BUCKET=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_FIREBASE_APP_ID=
```

### 3. Enable Google Sign-In

In the Firebase Console:
1. Go to **Authentication → Sign-in method**.
2. Enable the **Google** provider.

### 4. Enable Firestore

1. Go to **Firestore Database → Create database**.
2. Choose a location and start in **production mode** (or test mode for local dev).

### 5. Firestore security rules

For local development, a permissive rule set is helpful. **Do not use open rules in production.** Example rules that scope access to the user's own documents:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /videos/{id} {
      allow read, write: if request.auth != null
        && request.auth.uid == resource.data.userId;
    }
  }
}
```

> Note: `allow write` with `resource.data.userId` blocks the initial create (no existing doc yet). For Phase 1 local dev you may use full open rules, then tighten them in later phases. A more complete rule set is shown below.

Comprehensive rules for Phase 1:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /videos/{id} {
      allow create: if request.auth != null
        && request.resource.data.userId == request.auth.uid
        && request.resource.data.status == 'pending';
      allow read, update, delete: if request.auth != null
        && resource.data.userId == request.auth.uid;
    }
  }
}
```

### 6. Run the app

```bash
npm run dev
```

Open `http://localhost:5173` (or the URL Vite prints).

## Scripts

| Command            | Description                         |
| ------------------ | ----------------------------------- |
| `npm run dev`      | Start the Vite dev server           |
| `npm run build`    | Build for production                |
| `npm run preview`  | Preview the production build        |
| `npm run lint`     | Run oxlint                          |

## Folder Structure

```
src/
├── components/
│   ├── auth/          # RequireAuth route guard
│   ├── layout/        # DashboardLayout, Navbar, Workspace
│   └── video/         # NewVideo form, VideoFeed, VideoCard
├── config/            # firebase.js (Firebase init)
├── context/           # AuthContext (user state + Google sign-in)
├── hooks/             # useAuth, useVideos (real-time Firestore)
├── lib/               # videos.js (Firestore service)
├── pages/             # Landing (login), Dashboard
└── utils/             # constants.js, date.js
```

## Data Model

The `videos` collection stores one document per generation request:

| Field       | Type                        | Description                              |
| ----------- | --------------------------- | ---------------------------------------- |
| `userId`    | `string`                    | UID of the requesting user               |
| `topic`     | `string`                    | Video topic / prompt                     |
| `platform`  | `string`                    | `youtube_shorts`, `tiktok`, or `instagram_reels` |
| `status`    | `string`                    | `pending`, `processing`, `completed`, `failed` |
| `createdAt` | `Timestamp` (server)        | When the request was created             |
