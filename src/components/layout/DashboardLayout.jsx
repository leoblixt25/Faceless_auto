import Navbar from './Navbar'
import { Outlet } from 'react-router-dom'

export default function DashboardLayout() {
  return (
    <div className="min-h-screen bg-zinc-950">
      <Navbar />
      <Outlet />
    </div>
  )
}
