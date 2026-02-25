import { ShieldX } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function AccessDenied() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <ShieldX className="h-16 w-16 text-slate-300 mb-4" />
      <h2 className="text-xl font-semibold text-slate-800 mb-2">
        Access Denied
      </h2>
      <p className="text-slate-500 mb-6 max-w-md">
        You do not have permission to view this page. Contact your administrator
        if you believe this is an error.
      </p>
      <Button onClick={() => navigate('/dashboard')}>Back to Dashboard</Button>
    </div>
  )
}
