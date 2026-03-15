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

/**
 * Format a date string to M/D/YYYY h:mm AM/PM (no leading zeros)
 */
export function formatDateMDY(date: string | Date | null | undefined): string {
  if (!date) return '-'
  const d = new Date(date)
  if (isNaN(d.getTime())) return String(date)
  const month = d.getMonth() + 1
  const day = d.getDate()
  const year = d.getFullYear()
  let hours = d.getHours()
  const minutes = d.getMinutes().toString().padStart(2, '0')
  const ampm = hours >= 12 ? 'PM' : 'AM'
  hours = hours % 12 || 12
  return `${month}/${day}/${year} ${hours}:${minutes} ${ampm}`
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
