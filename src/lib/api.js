const WORKER_URL = import.meta.env.VITE_WORKER_URL || ''

/**
 * Dispatch a generate request to the Cloudflare Worker bridge.
 * If VITE_WORKER_URL is not configured, this resolves without calling
 * anything so local development still works.
 */
export async function dispatchVideoGeneration({ userId, topic, platform, documentId, duration }) {
  if (!WORKER_URL) {
    console.warn(
      'VITE_WORKER_URL is not set; skipping worker dispatch. ' +
        'Configure it in .env to enable cloud generation.',
    )
    return { skipped: true }
  }

  const response = await fetch(`${WORKER_URL}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userId, topic, platform, documentId, duration }),
  })

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.error || `Worker request failed (${response.status})`)
  }
  return data
}

export async function deleteVideo(documentId) {
  if (!WORKER_URL) {
    console.warn('VITE_WORKER_URL is not set; skipping delete dispatch.')
    return { skipped: true }
  }

  const response = await fetch(`${WORKER_URL}/api/video/${documentId}`, {
    method: 'DELETE',
  })

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.error || `Delete failed (${response.status})`)
  }
  return data
}
