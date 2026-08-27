import { Hono } from 'hono'
import {
  findPendingVideo,
  saveTiktokToken,
  updateVideoStatus,
} from './firebase'
import { dispatchGenerateVideo } from './github'
import { exchangeAuthCode } from './tiktok'
import type { Env } from './types'

const app = new Hono<{ Bindings: Env }>()

function corsHeaders(origin: string) {
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
  }
}

function isAllowedOrigin(env: Env, origin: string) {
  const allowed = (env.ALLOWED_ORIGIN || '').split(',').map((o) => o.trim())
  return allowed.includes(origin)
}

function getErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

type Step = {
  step: string
  ok?: boolean
  skipped?: boolean
  document?: string
  message?: string
  error?: string
  status?: number
  body?: string
}

app.use('*', async (c, next) => {
  const origin = c.req.header('origin')
  c.header('Vary', 'Origin')

  if (origin && isAllowedOrigin(c.env, origin)) {
    Object.entries(corsHeaders(origin)).forEach(([key, value]) => {
      c.header(key, value)
    })
  }

  // Handle CORS preflight.
  if (c.req.method === 'OPTIONS') {
    return c.body(null, 204)
  }

  await next()
})

app.get('/', (c) => c.json({ ok: true, service: 'faceless-worker' }))

app.post('/api/generate', async (c) => {
  let body: { userId?: string; topic?: string; platform?: string; documentId?: string }
  try {
    body = (await c.req.json()) as {
      userId?: string
      topic?: string
      platform?: string
      documentId?: string
    }
  } catch {
    return c.json({ error: 'Request body must be valid JSON.' }, 400)
  }

  const userId = typeof body.userId === 'string' ? body.userId.trim() : ''
  const topic = typeof body.topic === 'string' ? body.topic.trim() : ''
  const platform = typeof body.platform === 'string' ? body.platform.trim() : ''
  const documentId =
    typeof body.documentId === 'string' ? body.documentId.trim() : ''

  const allowedPlatforms = ['youtube_shorts', 'tiktok', 'instagram_reels'] as const
  if (!userId || !topic || !platform) {
    return c.json(
      { error: 'userId, topic, and platform are all required.' },
      400,
    )
  }
  if (!(allowedPlatforms as readonly string[]).includes(platform)) {
    return c.json(
      {
        error: `platform must be one of: ${allowedPlatforms.join(', ')}.`,
      },
      400,
    )
  }

  const clientPayload = {
    userId,
    topic,
    platform,
    documentId: '',
  }

  // Steps
  // 1) Securely update the matching Firestore document to "processing".
  // 2) Dispatch the GitHub repository_dispatch event.
  const steps: Step[] = []
  let status = 'pending'
  let documentName: string | null = null

  if (c.env.SKIP_FIRESTORE !== 'true') {
    try {
      if (documentId) {
        // Direct path update by the ID the frontend just created.
        // No composite index required.
        documentName = `videos/${documentId}`
        clientPayload.documentId = documentId
        await updateVideoStatus(c.env, documentName, 'processing')
        status = 'processing'
        steps.push({ step: 'firestore', ok: true, document: documentName })
      } else {
        // Fallback: locate the most recent pending video for the user.
        const doc = await findPendingVideo(c.env, userId)
        if (doc) {
          documentName = doc.name
          clientPayload.documentId = documentName.split('/').pop() || ''
          await updateVideoStatus(c.env, documentName, 'processing')
          status = 'processing'
          steps.push({ step: 'firestore', ok: true, document: documentName })
        } else {
          steps.push({
            step: 'firestore',
            ok: false,
            message: 'No pending video found for this user.',
          })
        }
      }
    } catch (err) {
      steps.push({ step: 'firestore', ok: false, error: getErrorMessage(err) })
    }
  } else {
    steps.push({ step: 'firestore', skipped: true })
  }

  // Always dispatch to GitHub (unless the caller only wanted a status check).
  try {
    const result = await dispatchGenerateVideo(c.env, clientPayload)
    steps.push({ step: 'github', ok: true, ...result })
  } catch (err) {
    steps.push({ step: 'github', ok: false, error: getErrorMessage(err) })
  }

  const allOk = steps.every((s) => s.ok || s.skipped)

  return c.json(
    {
      accepted: allOk,
      status,
      steps,
      client_payload: clientPayload,
    },
    allOk ? 202 : 502,
  )
})

app.post('/api/tiktok/token', async (c) => {
  let body: { userId?: string; code?: string }
  try {
    body = (await c.req.json()) as { userId?: string; code?: string }
  } catch {
    return c.json({ error: 'Request body must be valid JSON.' }, 400)
  }

  const userId = typeof body.userId === 'string' ? body.userId.trim() : ''
  const code = typeof body.code === 'string' ? body.code.trim() : ''
  if (!userId || !code) {
    return c.json({ error: 'userId and code are required.' }, 400)
  }

  const redirectUri = c.env.TIKTOK_REDIRECT_URI
  if (!redirectUri) {
    return c.json({ error: 'TIKTOK_REDIRECT_URI is not configured.' }, 500)
  }

  try {
    const token = await exchangeAuthCode(c.env, code, redirectUri)
    await saveTiktokToken(c.env, userId, token)
    return c.json({
      ok: true,
      openId: token.openId,
      expiresAt: token.expiresAt,
    })
  } catch (err) {
    return c.json({ ok: false, error: getErrorMessage(err) }, 502)
  }
})

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext) {
    // Serve the React app (static assets) for any non-API route.
    // API routes handled by Hono above.
    try {
      if (env.ASSETS) {
        const assetResponse = await env.ASSETS.fetch(request)
        return assetResponse
      }
    } catch {
      // fall through to Hono if asset serving fails
    }
    return app.fetch(request, env, ctx)
  },
}
