import NewVideo from '../video/NewVideo'
import VideoFeed from '../video/VideoFeed'
import { useVideos } from '../../hooks/useVideos'

export default function Workspace({ userId }) {
  const { videos, loading } = useVideos(userId)

  return (
    <div className="space-y-8">
      <NewVideo />
      <VideoFeed videos={videos} loading={loading} />
    </div>
  )
}
