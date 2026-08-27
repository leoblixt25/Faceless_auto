export const PLATFORMS = [
  { value: 'youtube_shorts', label: 'YouTube Shorts' },
  { value: 'tiktok', label: 'TikTok' },
  { value: 'instagram_reels', label: 'Instagram Reels' },
]

export const VIDEO_STATUS = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  POSTED: 'posted',
  FAILED: 'failed',
}

export const STATUS_LABELS = {
  [VIDEO_STATUS.PENDING]: 'Pending',
  [VIDEO_STATUS.PROCESSING]: 'Processing',
  [VIDEO_STATUS.COMPLETED]: 'Completed',
  [VIDEO_STATUS.POSTED]: 'Posted',
  [VIDEO_STATUS.FAILED]: 'Failed',
}
