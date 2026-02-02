import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date): string {
  if (!date) return '-'
  const d = new Date(date)
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(date: string | Date): string {
  if (!date) return '-'
  const d = new Date(date)
  return d.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function getStatusColor(status: string): string {
  const statusColors: Record<string, string> = {
    open: 'bg-warning text-warning-foreground',
    submitted: 'bg-success text-success-foreground',
    declined: 'bg-destructive text-destructive-foreground',
    'saved draft': 'bg-secondary text-secondary-foreground',
    draft: 'bg-secondary text-secondary-foreground',
    downloaded: 'bg-info text-info-foreground',
  }
  return statusColors[status.toLowerCase()] || 'bg-secondary text-secondary-foreground'
}

export function truncateText(text: string, maxLength: number): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}
