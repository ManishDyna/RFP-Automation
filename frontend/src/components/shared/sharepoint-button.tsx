import { useState } from 'react'
import { FolderOpen } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import type { ApiError } from '@/lib/api'

interface SharePointButtonProps {
  rfpId: string
  company?: string
  /** "icon" renders a compact square icon button; "labeled" renders the icon + "SharePoint Files" text. */
  variant?: 'icon' | 'labeled'
  className?: string
}

/**
 * Opens the SharePoint folder for an RFP in a new tab.
 * Resolves the folder webUrl on click via the backend, then redirects.
 * Caller is responsible for permission-gating (rfp.sharepoint.view).
 */
export function SharePointButton({
  rfpId,
  company,
  variant = 'icon',
  className,
}: SharePointButtonProps) {
  const [loading, setLoading] = useState(false)

  const handleClick = async () => {
    if (loading) return
    setLoading(true)
    try {
      const res = await api.getRfpSharePointUrl(rfpId, company)
      if (res?.url) {
        window.open(res.url, '_blank', 'noopener,noreferrer')
      } else {
        toast.error('SharePoint folder not available for this RFP.')
      }
    } catch (err) {
      const apiErr = err as ApiError
      if (apiErr?.status === 404) {
        toast.error('SharePoint folder not available for this RFP.')
      } else {
        toast.error(apiErr?.message || 'Could not open SharePoint folder.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (variant === 'labeled') {
    return (
      <Button
        size="sm"
        variant="outline"
        disabled={loading}
        onClick={handleClick}
        title="Open SharePoint folder for this RFP"
        className={
          className ??
          'h-8 border-slate-200 hover:bg-sky-50 hover:border-sky-300 hover:text-sky-700'
        }
      >
        <FolderOpen className={`h-3.5 w-3.5 mr-1.5 ${loading ? 'animate-pulse' : ''}`} />
        SharePoint Files
      </Button>
    )
  }

  return (
    <Button
      size="sm"
      variant="outline"
      disabled={loading}
      onClick={handleClick}
      title="Open SharePoint folder for this RFP"
      className={
        className ??
        'h-8 w-8 p-0 border-slate-200 hover:bg-sky-50 hover:border-sky-300 hover:text-sky-700'
      }
    >
      <FolderOpen className={`h-3.5 w-3.5 ${loading ? 'animate-pulse' : ''}`} />
    </Button>
  )
}
