import { useAuth } from './auth'
import Login from './pages/Login'
import Workspace from './pages/Workspace'

export default function App() {
  const { user, checking } = useAuth()

  if (checking) {
    return (
      <div className="min-h-full grid place-items-center">
        <span className="w-7 h-7 border-2 border-mist-400/30 border-t-brass-400 rounded-full animate-spin" />
      </div>
    )
  }

  return user ? <Workspace /> : <Login />
}
