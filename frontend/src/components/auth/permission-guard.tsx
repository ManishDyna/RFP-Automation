import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/use-auth'
import { useEffect } from 'react'

interface PermissionGuardProps {
  /** Single permission key or array of keys (any match grants access) */
  permission: string | string[]
  children: React.ReactNode
  fallback?: React.ReactNode
  redirectTo?: string
}

export function PermissionGuard({
  permission,
  children,
  fallback,
  redirectTo = '/dashboard',
}: PermissionGuardProps) {
  const user = useAuth((state) => state.user)
  const navigate = useNavigate()

  const permissions = Array.isArray(permission) ? permission : [permission]
  const hasPermission = permissions.some((p) => user?.permissions?.includes(p))

  useEffect(() => {
    if (!hasPermission && !fallback) {
      navigate(redirectTo, { replace: true })
    }
  }, [hasPermission, navigate, redirectTo, fallback])

  if (!hasPermission) {
    if (fallback) return <>{fallback}</>
    return null
  }

  return <>{children}</>
}
