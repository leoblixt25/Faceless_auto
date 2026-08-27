import { useEffect, useState } from 'react'
import { subscribeToUserVideos } from '../lib/videos'

export function useVideos(userId) {
  const [state, setState] = useState({ videos: [], ready: false })

  useEffect(() => {
    const unsubscribe = subscribeToUserVideos(userId, (data) => {
      setState({ videos: data, ready: true })
    })
    return unsubscribe
  }, [userId])

  return { videos: state.videos, loading: !state.ready }
}
