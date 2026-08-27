import type { Env } from './types'

const tokenEndpoint = 'https://open.tiktokapis.com/v2/oauth/token/'

export interface TikTokToken {
  accessToken: string
  refreshToken?: string
  openId?: string
  expiresAt: string
}

/**
 * Exchange a TikTok OAuth authorization code for an access token.
 * Runs server-side so the client secret is never exposed to the browser.
 */
export async function exchangeAuthCode(
  env: Env,
  code: string,
  redirectUri: string,
): Promise<TikTokToken> {
  if (!env.TIKTOK_CLIENT_KEY || !env.TIKTOK_CLIENT_SECRET) {
    throw new Error('Missing TIKTOK_CLIENT_KEY or TIKTOK_CLIENT_SECRET.')
  }

  const body = new URLSearchParams({
    client_key: env.TIKTOK_CLIENT_KEY,
    client_secret: env.TIKTOK_CLIENT_SECRET,
    code,
    grant_type: 'authorization_code',
    redirect_uri: redirectUri,
  })

  const response = await fetch(tokenEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })

  const data = (await response.json()) as {
    access_token?: string
    refresh_token?: string
    open_id?: string
    expires_in?: number
    error?: string
    error_description?: string
  }

  if (!response.ok || !data.access_token) {
    const message =
      data.error_description || data.error || `TikTok exchange failed (${response.status})`
    throw new Error(message)
  }

  const expiresAt = new Date(
    Date.now() + (data.expires_in || 86400) * 1000,
  ).toISOString()

  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    openId: data.open_id,
    expiresAt,
  }
}
