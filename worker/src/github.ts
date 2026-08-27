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
