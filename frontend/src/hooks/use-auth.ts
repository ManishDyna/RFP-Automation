import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '@/lib/api'

interface User {
  id?: string
  record_id?: string
  name: string
  email: string
  role: string
  mobile?: string
  permissions?: string[]
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  checkSession: () => Promise<void>
  setUser: (user: User | null) => void
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,

      login: async (email: string, password: string) => {
        const result = await api.login(email, password)
        // The session is set by the backend via cookies
        // We need to fetch the user data after login
        const sessionStatus = await api.getSessionStatus()
        if (sessionStatus.valid && sessionStatus.user) {
          set({
            user: sessionStatus.user,
            isAuthenticated: true,
            isLoading: false,
          })
        }
      },

      logout: async () => {
        await api.logout()
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        })
      },

      checkSession: async () => {
        try {
          set({ isLoading: true })
          const sessionStatus = await api.getSessionStatus()
          if (sessionStatus.valid && sessionStatus.user) {
            set({
              user: sessionStatus.user,
              isAuthenticated: true,
              isLoading: false,
            })
          } else {
            set({
              user: null,
              isAuthenticated: false,
              isLoading: false,
            })
          }
        } catch {
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
          })
        }
      },

      setUser: (user) => {
        set({
          user,
          isAuthenticated: !!user,
          isLoading: false,
        })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)

// Helper hook to check if user is admin
export function useIsAdmin(): boolean {
  const user = useAuth((state) => state.user)
  return user?.role?.toLowerCase() === 'admin'
}

// Helper hook to check if user has a specific permission
export function useHasPermission(permission: string): boolean {
  const user = useAuth((state) => state.user)
  if (!user) return false
  // Admin always has all permissions
  if (user.role?.toLowerCase() === 'admin') return true
  return user.permissions?.includes(permission) ?? false
}
