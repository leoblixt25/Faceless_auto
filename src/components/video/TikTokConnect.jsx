import { useAuth } from '../../context/AuthContext'

export default function TikTokConnect() {
  const { user } = useAuth()

  const clientKey = import.meta.env.VITE_TIKTOK_CLIENT_KEY || ''
  const redirectUri = import.meta.env.VITE_TIKTOK_REDIRECT_URI || ''
  const installed = clientKey && redirectUri

  const handleConnect = () => {
    // State (CSRF) carries our user id so we can map the token on callback.
    const state = encodeURIComponent(user.uid)
    const scopes = encodeURIComponent('video.publish,user.info.basic')
    const csrf = encodeURIComponent(state)
    const url =
      `https://www.tiktok.com/v2/auth/authorize/` +
      `?client_key=${encodeURIComponent(clientKey)}` +
      `&scope=${scopes}` +
      `&response_type=code` +
      `&redirect_uri=${encodeURIComponent(redirectUri)}` +
      `&state=${csrf}`
    window.location.href = url
  }

  if (!installed) {
    return null
  }

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5">
      <h2 className="text-sm font-semibold text-white">TikTok Publishing</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Connect your TikTok account so generated videos can be published as
        TikToks. The access token expires after 24 hours and is stored securely
        server-side.
      </p>

      <button
        type="button"
        onClick={handleConnect}
        className="mt-4 inline-flex items-center gap-2 rounded-xl bg-black px-4 py-2.5 text-sm font-semibold text-white ring-1 ring-zinc-700 transition hover:bg-zinc-900"
      >
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M16.6 5.8A4.8 4.8 0 0114.9 2h-3.2v13.3a2.9 2.9 0 11-2.9-2.9c.3 0 .6 0 .9.1V9.3a6.1 6.1 0 00-.9-.1 6.1 6.1 0 106.1 6.1V8.5a7.8 7.8 0 004.6 1.5V6.8a4.7 4.7 0 01-1.9-1z" />
        </svg>
        Connect TikTok
      </button>
    </div>
  )
}
