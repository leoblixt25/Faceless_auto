import { useState } from 'react'
import { VIDEO_STATUS, STATUS_LABELS, PLATFORMS, DURATION_OPTIONS } from '../../utils/constants'
import { formatDate } from '../../utils/date'
import { deleteVideo } from '../../lib/api'

const STATUS_STYLES = {
  [VIDEO_STATUS.PENDING]: {
    dot: 'bg-amber-400',
    badge: 'bg-amber-500/10 text-amber-400 ring-amber-500/30',
    label: 'Queued',
  },
  [VIDEO_STATUS.PROCESSING]: {
    dot: 'bg-sky-400',
    badge: 'bg-sky-500/10 text-sky-400 ring-sky-500/30',
    label: 'Processing',
  },
  [VIDEO_STATUS.COMPLETED]: {
    dot: 'bg-emerald-400',
    badge: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/30',
    label: 'Completed',
  },
  [VIDEO_STATUS.POSTED]: {
    dot: 'bg-purple-400',
    badge: 'bg-purple-500/10 text-purple-400 ring-purple-500/30',
    label: 'Posted',
  },
  [VIDEO_STATUS.FAILED]: {
    dot: 'bg-red-400',
    badge: 'bg-red-500/10 text-red-400 ring-red-500/30',
    label: 'Failed',
  },
}

const PLATFORM_ICONS = {
  youtube_shorts: (
    <path d="M23 12s0-3.2-.4-4.7a2.5 2.5 0 00-1.8-1.8C19.3 5 12 5 12 5s-7.3 0-8.8.5A2.5 2.5 0 001.4 7.3 26 26 0 001 12a26 26 0 00.4 4.7 2.5 2.5 0 001.8 1.8c1.5.5 8.8.5 8.8.5s7.3 0 8.8-.5a2.5 2.5 0 001.8-1.8c.4-1.5.4-4.7.4-4.7zM9.8 15.3V8.7l5.9 3.3-5.9 3.3z" />
  ),
  tiktok: (
    <path d="M16.6 5.8A4.8 4.8 0 0114.9 2h-3.2v13.3a2.9 2.9 0 11-2.9-2.9c.3 0 .6 0 .9.1V9.3a6.1 6.1 0 00-.9-.1 6.1 6.1 0 106.1 6.1V8.5a7.8 7.8 0 004.6 1.5V6.8a4.7 4.7 0 01-1.9-1z" />
  ),
  instagram_reels: (
    <path d="M12 2c2.7 0 3 0 4.1.1 1.1.1 1.8.2 2.4.5.7.2 1.2.5 1.7 1 .5.5.8 1 1 1.7.2.6.4 1.3.5 2.4.1 1.1.1 1.4.1 4.1s0 3-.1 4.1c-.1 1.1-.2 1.8-.5 2.4a4.6 4.6 0 01-1 1.7c-.5.5-1 .8-1.7 1-.6.2-1.3.4-2.4.5-1.1.1-1.4.1-4.1.1s-3 0-4.1-.1c-1.1-.1-1.8-.2-2.4-.5a4.6 4.6 0 01-1.7-1 4.6 4.6 0 01-1-1.7c-.2-.6-.4-1.3-.5-2.4C2 15 2 14.7 2 12s0-3 .1-4.1c.1-1.1.2-1.8.5-2.4a4.6 4.6 0 011-1.7 4.6 4.6 0 011.7-1c.6-.2 1.3-.4 2.4-.5C9 2 9.3 2 12 2zm0 3.2c-2.4 0-2.7 0-3.6 0-1 0-1.5.2-1.9.3l-.3.1-.3.3a4.8 4.8 0 00-.3 3.5c.8 2.4 3 4.1 5.6 4.1a4.3 4.3 0 002.2-.6l-.1-.1c-.5-.4-.9-.9-1.3-1.5-.3.2-.6.3-.9.3a3.7 3.7 0 110-7.4c.9 0 1.2.6 1.6 1.2V9L12 8.9v-2.1h3.9v-1.8h-.2a16 16 0 00-3.7-.6zm5.6 3.4a4.3 4.3 0 01-1.8.4v1.9a4.3 4.3 0 01-4.3 4.3c-.6 0-1.2-.1-1.7-.4-.4 2.6.8 4.5 3.4 4.5a3.7 3.7 0 003.7-3.7V7.6c.3.3.5.5.7.6 0 0 0 .2 0 .4zM12 4.3v2-2z" />
  ),
}

function PlatformIcon({ value }) {
  return (
    <svg
      className="h-5 w-5 text-zinc-400"
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      {PLATFORM_ICONS[value] || null}
    </svg>
  )
}

export default function VideoCard({ video }) {
  const platform = PLATFORMS.find((p) => p.value === video.platform)
  const status = STATUS_STYLES[video.status] || STATUS_STYLES[VIDEO_STATUS.PENDING]
  const isProcessing = video.status === VIDEO_STATUS.PROCESSING
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const durationLabel =
    DURATION_OPTIONS.find((d) => d.value === video.duration)?.label ||
    (video.duration ? `~${video.duration}s` : null)

  const handleDelete = async () => {
    if (deleting) return
    const confirmed = window.confirm(
      'Delete this video? This also removes the stored file and cannot be undone.',
    )
    if (!confirmed) return

    setDeleting(true)
    setDeleteError('')
    try {
      await deleteVideo(video.id)
    } catch (err) {
      console.error('Failed to delete video:', err)
      setDeleteError('Could not delete. Please try again.')
      setDeleting(false)
    }
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-800">
            <PlatformIcon value={video.platform} />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">
              {platform ? platform.label : 'Unknown Platform'}
            </p>
            <p className="text-xs text-zinc-500">
              {formatDate(video.createdAt)}
              {durationLabel ? ` · ${durationLabel}` : ''}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            title="Delete video"
            className="rounded-lg p-1.5 text-zinc-500 transition hover:bg-red-500/10 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <svg
              className="h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2m2 0v14a1 1 0 01-1 1H6a1 1 0 01-1-1V6m4 5v6m4-6v6" />
            </svg>
          </button>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${status.badge}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${status.dot} ${isProcessing ? 'animate-pulse' : ''}`} />
            {STATUS_LABELS[video.status] || status.label}
          </span>
        </div>
      </div>

      <p className="mt-4 line-clamp-2 text-sm leading-relaxed text-zinc-300">
        {video.topic}
      </p>

      {deleting && (
        <p className="mt-3 text-xs text-zinc-500">Deleting…</p>
      )}
      {deleteError && <p className="mt-3 text-xs text-red-400">{deleteError}</p>}

      {video.videoUrl && (
        <div className="mt-4">
          <video
            src={video.videoUrl}
            controls
            preload="metadata"
            className="w-full rounded-xl border border-zinc-800 bg-black"
          />
          <a
            href={video.videoUrl}
            target="_blank"
            rel="noopener noreferrer"
            download
            className="mt-2 inline-block text-sm font-medium text-purple-400 transition hover:text-purple-300"
          >
            Download / open video →
          </a>
        </div>
      )}

      {video.socialLink && (
        <a
          href={video.socialLink}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-block text-sm font-medium text-purple-400 transition hover:text-purple-300"
        >
          View on {platform ? platform.label : 'platform'} →
        </a>
      )}
    </div>
  )
}
