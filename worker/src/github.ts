import type { Env, ClientPayload } from './types'

const githubApi = 'https://api.github.com'

/**
 * Trigger a GitHub Actions `repository_dispatch` event.
 * The workflow listens for event_type "generate-video".
 */
export async function dispatchGenerateVideo(
  env: Env,
  payload: ClientPayload,
): Promise<{ status: number; body: string }> {
  if (!env.GITHUB_PAT) {
    throw new Error('Missing GITHUB_PAT secret.')
  }

  const repo = env.GITHUB_REPO
  if (!repo) {
    throw new Error('Missing GITHUB_REPO environment variable.')
  }

  const url = `${githubApi}/repos/${repo}/dispatches`

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.GITHUB_PAT}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
      'User-Agent': 'faceless-worker',
    },
    body: JSON.stringify({
      event_type: 'generate-video',
      client_payload: payload,
    }),
  })

  const text = await response.text()

  if (!response.ok) {
    throw new Error(`GitHub dispatch failed (${response.status}): ${text}`)
  }

  return { status: response.status, body: text }
}

function githubHeaders(env: Env): Record<string, string> {
  return {
    Authorization: `Bearer ${env.GITHUB_PAT}`,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'faceless-worker',
  }
}

/**
 * Delete the GitHub Release (and its uploaded video asset) for a given video
 * document id. Release tag format is `v-<documentId>`. Best-effort: a missing
 * release is treated as already deleted.
 */
export async function deleteRelease(
  env: Env,
  documentId: string,
): Promise<{ status: number; deleted: boolean }> {
  if (!env.GITHUB_PAT) {
    throw new Error('Missing GITHUB_PAT secret.')
  }
  const repo = env.GITHUB_REPO
  if (!repo) {
    throw new Error('Missing GITHUB_REPO environment variable.')
  }

  const tag = `v-${documentId}`
  const getUrl = `${githubApi}/repos/${repo}/releases/tags/${encodeURIComponent(tag)}`
  const getResp = await fetch(getUrl, { headers: githubHeaders(env) })

  if (getResp.status === 404) {
    return { status: 404, deleted: false }
  }
  if (!getResp.ok) {
    const text = await getResp.text()
    throw new Error(`GitHub release lookup failed (${getResp.status}): ${text}`)
  }

  const release = (await getResp.json()) as { id?: number }
  if (!release.id) {
    return { status: 404, deleted: false }
  }

  const delUrl = `${githubApi}/repos/${repo}/releases/${release.id}`
  const delResp = await fetch(delUrl, {
    method: 'DELETE',
    headers: githubHeaders(env),
  })

  if (!delResp.ok && delResp.status !== 404) {
    const text = await delResp.text()
    throw new Error(`GitHub release delete failed (${delResp.status}): ${text}`)
  }

  return { status: delResp.status, deleted: true }
}
