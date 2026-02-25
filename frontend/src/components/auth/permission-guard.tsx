import { useNavigate } from 'react-router-dom'
import { useHasPermission } from '@/hooks/use-auth'
import { useEffect } from 'react'

interface PermissionGuardProps {
  permission: string
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
  const hasPermission = useHasPermission(permission)
  const navigate = useNavigate()

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
