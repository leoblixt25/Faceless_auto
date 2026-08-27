/**
 * Firebase REST helpers for Cloudflare Workers.
 *
 * The Firebase Admin SDK cannot run in the Workers runtime (it depends on
 * Node-only APIs), so this module mints a short-lived OAuth2 access token from
 * a service-account credential and talks to Firestore over its REST API.
 */
import type { Env, ServiceAccount } from './types'

const tokenEndpoint = 'https://oauth2.googleapis.com/token'

let cachedPrivateKey: CryptoKey | null = null
let cachedKeyId: string | null = null

/** Parse the service-account JSON stored in the FIREBASE_CREDENTIALS secret. */
function getCredentials(env: Env): ServiceAccount {
  if (!env.FIREBASE_CREDENTIALS) {
    throw new Error('Missing FIREBASE_CREDENTIALS secret.')
  }
  let creds: ServiceAccount
  try {
    creds = JSON.parse(env.FIREBASE_CREDENTIALS) as ServiceAccount
  } catch {
    throw new Error('FIREBASE_CREDENTIALS secret is not valid JSON.')
  }
  if (!creds.client_email || !creds.private_key || !creds.project_id) {
    throw new Error(
      'FIREBASE_CREDENTIALS is missing client_email, private_key, or project_id.',
    )
  }
  return creds
}

/** Import the service-account RSA private key (PEM) as a WebCrypto CryptoKey. */
async function getPrivateKey(creds: ServiceAccount): Promise<CryptoKey> {
  if (cachedPrivateKey && cachedKeyId === creds.private_key) {
    return cachedPrivateKey
  }

  const pem = creds.private_key
  const base64 = pem
    .replace('-----BEGIN PRIVATE KEY-----', '')
    .replace('-----END PRIVATE KEY-----', '')
    .replace(/\s+/g, '')
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }

  const key = await crypto.subtle.importKey(
    'pkcs8',
    bytes.buffer,
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['sign'],
  )

  cachedPrivateKey = key
  cachedKeyId = creds.private_key
  return key
}

function base64UrlEncode(input: unknown): string {
  const str = typeof input === 'string' ? input : JSON.stringify(input)
  const bytes = new TextEncoder().encode(str as string)
  let binary = ''
  for (const byte of bytes) {
    binary += String.fromCharCode(byte)
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

async function signJwt(payload: object, privateKey: CryptoKey): Promise<string> {
  const header = { alg: 'RS256', typ: 'JWT' }
  const signingInput = `${base64UrlEncode(header)}.${base64UrlEncode(payload)}`
  const signature = await crypto.subtle.sign(
    'RSASSA-PKCS1-v1_5',
    privateKey,
    new TextEncoder().encode(signingInput),
  )
  const signatureB64 = btoa(String.fromCharCode(...new Uint8Array(signature)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
  return `${signingInput}.${signatureB64}`
}

/** Mint a short-lived OAuth2 access token for the service account. */
async function getAccessToken(creds: ServiceAccount): Promise<string> {
  const now = Math.floor(Date.now() / 1000)
  const jwt = await signJwt(
    {
      iss: creds.client_email,
      scope: 'https://www.googleapis.com/auth/datastore',
      aud: tokenEndpoint,
      iat: now,
      exp: now + 3600,
    },
    await getPrivateKey(creds),
  )

  const body = new URLSearchParams({
    grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
    assertion: jwt,
  })

  const response = await fetch(tokenEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Failed to mint OAuth token (${response.status}): ${text}`)
  }

  const data = (await response.json()) as { access_token?: string }
  if (!data.access_token) {
    throw new Error('OAuth token response did not include an access_token.')
  }
  return data.access_token
}

/** Build the Firestore REST document path for the videos collection. */
function firestoreRoot(creds: ServiceAccount): string {
  return `https://firestore.googleapis.com/v1/projects/${creds.project_id}/databases/(default)/documents`
}

interface QueryResult {
  document?: { name: string; fields: Record<string, unknown> }
}

interface Document {
  name: string
  fields: Record<string, unknown>
}

/**
 * Find the most recent "pending" video document for a user and return its
 * full resource name (project path). Returns null if none is found.
 */
export async function findPendingVideo(
  env: Env,
  userId: string,
): Promise<Document | null> {
  const creds = getCredentials(env)
  const token = await getAccessToken(creds)

  const structuredQuery = {
    structuredQuery: {
      from: [{ collectionId: 'videos' }],
      where: {
        compositeFilter: {
          op: 'AND',
          filters: [
            {
              fieldFilter: {
                field: { fieldPath: 'userId' },
                op: 'EQUAL',
                value: { stringValue: userId },
              },
            },
            {
              fieldFilter: {
                field: { fieldPath: 'status' },
                op: 'EQUAL',
                value: { stringValue: 'pending' },
              },
            },
          ],
        },
      },
      orderBy: [{ field: { fieldPath: 'createdAt' }, direction: 'DESCENDING' }],
      limit: 1,
    },
  }

  const url = `${firestoreRoot(creds)}:runQuery`
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(structuredQuery),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Firestore query failed (${response.status}): ${text}`)
  }

  const results = (await response.json()) as QueryResult[]
  const doc = results.find((r) => r.document)
  return doc ? (doc.document as Document) : null
}

/** Update a Firestore document's `status` field. */
export async function updateVideoStatus(
  env: Env,
  documentName: string,
  status: string,
): Promise<unknown> {
  const creds = getCredentials(env)
  const token = await getAccessToken(creds)

  const url = `${firestoreRoot(creds)}/${documentName}?updateMask.fieldPaths=status&updateMask.fieldPaths=updatedAt`
  const now = new Date().toISOString()
  const body = {
    fields: {
      status: { stringValue: status },
      updatedAt: { timestampValue: now },
    },
  }

  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Firestore update failed (${response.status}): ${text}`)
  }

  return response.json()
}

/** Store (or update) the user's TikTok OAuth token in the tiktok_tokens collection.
 *  A single PATCH creates the document if missing and applies the update mask.
 */
export async function saveTiktokToken(
  env: Env,
  userId: string,
  tokenData: {
    accessToken: string
    refreshToken?: string
    openId?: string
    expiresAt: string
  },
): Promise<string> {
  const creds = getCredentials(env)
  const token = await getAccessToken(creds)

  const docPath = encodeURIComponent(userId)
  const mask =
    'updateMask.fieldPaths=accessToken&updateMask.fieldPaths=refreshToken' +
    '&updateMask.fieldPaths=openId&updateMask.fieldPaths=expiresAt' +
    '&updateMask.fieldPaths=updatedAt'
  const url = `${firestoreRoot(creds)}/tiktok_tokens/${docPath}?${mask}`

  const fields: Record<string, unknown> = {
    accessToken: { stringValue: tokenData.accessToken },
    expiresAt: { stringValue: tokenData.expiresAt },
    updatedAt: { timestampValue: new Date().toISOString() },
  }
  if (tokenData.refreshToken) {
    fields.refreshToken = { stringValue: tokenData.refreshToken }
  }
  if (tokenData.openId) {
    fields.openId = { stringValue: tokenData.openId }
  }

  const response = await fetch(url, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ fields }),
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(
      `Firestore token save failed (${response.status}): ${text}`,
    )
  }

  return userId
}

/** Delete a video document from Firestore by its document id (via service account). */
export async function deleteVideoDoc(env: Env, documentId: string): Promise<void> {
  const creds = getCredentials(env)
  const token = await getAccessToken(creds)

  const url = `${firestoreRoot(creds)}/videos/${encodeURIComponent(documentId)}`
  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })

  if (!response.ok && response.status !== 404) {
    const text = await response.text()
    throw new Error(`Firestore delete failed (${response.status}): ${text}`)
  }
}
