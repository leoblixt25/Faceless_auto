import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

export default function TikTokCallback() {
  const location = useLocation()
  const [state, setState] = useState('processing') // processing | success | error
  const [message, setMessage] = useState('Linking your TikTok account...')

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const code = params.get('code')
    const stateParam = params.get('state')
    const error = params.get('error')

    const exchange = async () => {
      if (error) {
        setState('error')
        setMessage(error)
        return
      }
      if (!code) {
        setState('error')
        setMessage('Missing authorization code from TikTok.')
        return
      }

      const workerUrl = import.meta.env.VITE_WORKER_URL
      if (!workerUrl) {
        setState('error')
        setMessage('VITE_WORKER_URL is not configured. Cannot complete OAuth.')
        return
      }

      try {
        const response = await fetch(`${workerUrl}/api/tiktok/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ userId: stateParam, code }),
        })
        const data = await response.json()
        if (!response.ok || !data.ok) {
          setState('error')
          setMessage(data.error || 'TikTok token exchange failed.')
          return
        }
        setState('success')
        setMessage('Your TikTok account is connected.')
      } catch {
        setState('error')
        setMessage('Network error while connecting TikTok.')
      }
    }

    exchange()
  }, [location.search])

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950 px-6">
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900/60 p-8 text-center">
        {state === 'processing' && (
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-white" />
        )}
        {state === 'success' && (
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M16.7 5.3a1 1 0 010 1.4l-7 7a1 1 0 01-1.4 0l-3-3a1 1 0 111.4-1.4l2.3 2.3 6.3-6.3a1 1 0 011.4 0z"
                clipRule="evenodd"
              />
            </svg>
          </div>
        )}
        {state === 'error' && (
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-red-500/20 text-red-400">
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.7 7.3a1 1 0 000 1.4L8.6 9l.1-.1a1 1 0 010 1.4L8.7 10.3a1 1 0 01-1.4-1.4l.1-.1-.1.1a1 1 0 010-1.4 1 1 0 011.4 0zM11.3 7.3a1 1 0 011.4 1.4L10 11.4a1 1 0 01-1.4-1.4l2.7-2.7z"
                clipRule="evenodd"
              />
            </svg>
          </div>
        )}

        <h1 className="text-xl font-bold text-white">
          {state === 'processing' && 'Connecting TikTok'}
          {state === 'success' && 'Success'}
          {state === 'error' && 'Something went wrong'}
        </h1>
        <p className="mt-2 text-sm text-zinc-400">{message}</p>

        <Link
          to="/dashboard"
          className="mt-6 inline-block rounded-xl bg-purple-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-purple-500"
        >
          Back to Dashboard
        </Link>
      </div>
    </div>
  )
}
