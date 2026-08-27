import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { PLATFORMS, DURATION_OPTIONS } from '../../utils/constants'
import { createVideo } from '../../lib/videos'
import { dispatchVideoGeneration } from '../../lib/api'

export default function NewVideo() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')
  const [platform, setPlatform] = useState(PLATFORMS[0].value)
  const [duration, setDuration] = useState(DURATION_OPTIONS[0].value)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!topic.trim()) return

    setSubmitting(true)
    setError('')
    try {
      const documentId = await createVideo({
        userId: user.uid,
        topic: topic.trim(),
        platform,
        duration,
        status: 'pending',
      })

      // Kick off the cloud pipeline through the Worker bridge.
      await dispatchVideoGeneration({
        userId: user.uid,
        topic: topic.trim(),
        platform,
        documentId,
        duration,
      })

      setTopic('')
    } catch (err) {
      console.error('Failed to submit video request:', err)
      setError('Failed to submit your request. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6">
      <h2 className="text-lg font-semibold text-white">New Video</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Describe the faceless video you want to generate.
      </p>

      <form onSubmit={handleSubmit} className="mt-5 space-y-5">
        <div>
          <label htmlFor="topic" className="mb-1.5 block text-sm font-medium text-zinc-300">
            Video Topic or Prompt
          </label>
          <textarea
            id="topic"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            placeholder="e.g. Top 5 surprising facts about deep sea creatures"
            rows={4}
            className="w-full resize-none rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-white placeholder-zinc-500 outline-none transition focus:border-purple-500 focus:ring-2 focus:ring-purple-500/30"
          />
        </div>

        <div>
          <label htmlFor="platform" className="mb-1.5 block text-sm font-medium text-zinc-300">
            Target Platform
          </label>
          <select
            id="platform"
            value={platform}
            onChange={(event) => setPlatform(event.target.value)}
            className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-white outline-none transition focus:border-purple-500 focus:ring-2 focus:ring-purple-500/30"
          >
            {PLATFORMS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="duration" className="mb-1.5 block text-sm font-medium text-zinc-300">
            Video Length
          </label>
          <select
            id="duration"
            value={duration}
            onChange={(event) => setDuration(Number(event.target.value))}
            className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-white outline-none transition focus:border-purple-500 focus:ring-2 focus:ring-purple-500/30"
          >
            {DURATION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="rounded-xl px-4 py-2.5 text-sm font-medium text-zinc-400 transition hover:text-white"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !topic.trim()}
            className="rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-purple-900/40 transition hover:from-purple-500 hover:to-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? 'Submitting...' : 'Generate Video'}
          </button>
        </div>
      </form>
    </div>
  )
}
