import { useAuth } from '../context/AuthContext'
import Workspace from '../components/layout/Workspace'

export default function Dashboard() {
  const { user } = useAuth()
  const firstName = user?.displayName?.split(' ')[0] || 'creator'

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Welcome back, {firstName}!</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Create and track your faceless short videos.
        </p>
      </div>

      <Workspace userId={user.uid} />
    </div>
  )
}
