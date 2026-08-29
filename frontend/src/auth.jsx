import { createContext, useContext, useEffect, useState } from 'react'
import { api, clearToken, getToken, setToken } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    if (!getToken()) { setChecking(false); return }
    api.me()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setChecking(false))
  }, [])

  const login = async (email, password) => {
    const data = await api.login(email, password)
    setToken(data.access_token)
    setUser(await api.me())
  }

  const register = async (username, email, password) => {
    const data = await api.register(username, email, password)
    setToken(data.access_token)
    setUser(await api.me())
  }

  const logout = () => { clearToken(); setUser(null) }

  return (
    <AuthContext.Provider value={{ user, checking, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
