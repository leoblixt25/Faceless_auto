import { useState } from 'react'
import { useAuth } from '../../context/AuthContext'

function getInitials(name) {
  if (!name) return '?'
  return name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

export default function Navbar() {
  const { user, logout } = useAuth()
  const [error, setError] = useState('')

  const handleLogout = async () => {
    setError('')
    try {
      await logout()
    } catch {
      setError('Failed to log out.')
    }
  }

  return (
    <header className="sticky top-0 z-10 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-purple-500 to-indigo-500">
            <svg
              className="h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            </svg>
          </div>
          <span className="text-sm font-semibold text-white">Faceless Studio</span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5">
            {user?.photoURL ? (
              <img
                src={user.photoURL}
                alt={user.displayName || 'User avatar'}
                className="h-8 w-8 rounded-full object-cover"
              />
            ) : (
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-700 text-xs font-semibold text-white">
                {getInitials(user?.displayName)}
              </div>
            )}
            <div className="hidden sm:block">
              <p className="text-sm font-medium leading-tight text-white">
                {user?.displayName || 'User'}
              </p>
              <p className="text-xs leading-tight text-zinc-500">{user?.email}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={handleLogout}
            className="rounded-lg border border-zinc-700 px-3.5 py-2 text-sm font-medium text-zinc-300 transition hover:border-zinc-600 hover:text-white"
          >
            Log out
          </button>
        </div>
      </div>

      {error && (
        <div className="border-t border-zinc-800 bg-red-500/10 px-6 py-2 text-center text-sm text-red-400">
          {error}
        </div>
      )}
    </header>
  )
}
