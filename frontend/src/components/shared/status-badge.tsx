import {
  Clock,
  CheckCircle2,
  XCircle,
  ListFilter,
  Download,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'

export function StatusBadge({ status }: { status: string }) {
  const statusMap: Record<string, { label: string; variant: 'warning' | 'success' | 'destructive' | 'secondary' | 'info'; icon: React.ElementType }> = {
    open: { label: 'Open', variant: 'warning', icon: Clock },
    not_participant: { label: 'Not Participant', variant: 'destructive', icon: XCircle },
    submitted: { label: 'Submitted', variant: 'success', icon: CheckCircle2 },
    declined: { label: 'Declined', variant: 'destructive', icon: XCircle },
    'saved draft': { label: 'Saved Draft', variant: 'secondary', icon: ListFilter },
    downloaded: { label: 'Downloaded', variant: 'info', icon: Download },
    draft: { label: 'Draft', variant: 'secondary', icon: ListFilter },
  }

  const { label, variant, icon: Icon } = statusMap[status?.toLowerCase()] || {
    label: status || 'Unknown',
    variant: 'secondary' as const,
    icon: ListFilter
  }

  return (
    <Badge variant={variant} className="gap-1.5 font-medium">
      <Icon className="h-3 w-3" />
      {label}
    </Badge>
  )
}
