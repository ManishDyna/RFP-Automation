import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ScrollText,
  Search,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { useHasPermission } from '@/hooks/use-auth'

const CATEGORIES = ['', 'AUTH', 'USER', 'ROLE', 'RFP', 'SYSTEM']
const ACTIONS = [
  '',
  'LOGIN',
  'LOGOUT',
  'LOGIN_FAILED',
  'PASSWORD_CHANGED',
  'PASSWORD_RESET',
  'USER_CREATED',
  'USER_UPDATED',
  'USER_DELETED',
  'USER_ACTIVATED',
  'USER_DEACTIVATED',
  'USER_UNLOCKED',
  'ROLE_CREATED',
  'ROLE_UPDATED',
  'ROLE_DELETED',
  'ROLE_PERMISSIONS_UPDATED',
  'SEED_ROLES',
]

const categoryColors: Record<string, string> = {
  AUTH: 'bg-blue-100 text-blue-700',
  USER: 'bg-green-100 text-green-700',
  ROLE: 'bg-purple-100 text-purple-700',
  RFP: 'bg-orange-100 text-orange-700',
  SYSTEM: 'bg-slate-100 text-slate-700',
}

export default function AuditLogsPage() {
  const hasPermission = useHasPermission('audit_logs.view')
  const [page, setPage] = useState(1)
  const [pageSize] = useState(30)
  const [category, setCategory] = useState('')
  const [action, setAction] = useState('')
  const [actorEmail, setActorEmail] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', page, pageSize, category, action, actorEmail, dateFrom, dateTo],
    queryFn: () =>
      api.getAuditLogs({
        page,
        page_size: pageSize,
        category,
        action,
        actor_email: actorEmail,
        date_from: dateFrom,
        date_to: dateTo,
      }),
    placeholderData: (prev) => prev,
  })

  const logs = data?.logs || []
  const totalPages = data?.total_pages || 0
  const total = data?.total || 0

  function formatTimestamp(ts: string) {
    if (!ts) return '-'
    try {
      const d = new Date(ts)
      return d.toLocaleString()
    } catch {
      return ts
    }
  }

  function parseDetails(details: string) {
    if (!details) return null
    try {
      return JSON.parse(details)
    } catch {
      return details
    }
  }

  if (!hasPermission) return null

  return (
    <PageWrapper
      title="Audit Trail"
      description={`Activity logs for authentication, user management, and system events${total > 0 ? ` (${total} total)` : ''}`}
    >
      <Card>
        <CardContent className="p-6">
          {/* Filters */}
          <div className="flex flex-wrap items-end gap-3 mb-6">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500">Category</label>
              <Select value={category} onValueChange={(v) => { setCategory(v === 'all' ? '' : v); setPage(1) }}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  {CATEGORIES.filter(Boolean).map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500">Action</label>
              <Select value={action} onValueChange={(v) => { setAction(v === 'all' ? '' : v); setPage(1) }}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  {ACTIONS.filter(Boolean).map((a) => (
                    <SelectItem key={a} value={a}>{a.replace(/_/g, ' ')}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500">Actor Email</label>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                <Input
                  placeholder="Filter by email..."
                  value={actorEmail}
                  onChange={(e) => { setActorEmail(e.target.value); setPage(1) }}
                  className="w-[200px] pl-8"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500">From</label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
                className="w-[150px]"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-500">To</label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
                className="w-[150px]"
              />
            </div>

            {(category || action || actorEmail || dateFrom || dateTo) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setCategory('')
                  setAction('')
                  setActorEmail('')
                  setDateFrom('')
                  setDateTo('')
                  setPage(1)
                }}
              >
                Clear Filters
              </Button>
            )}
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <ScrollArea className="h-[calc(100vh-380px)]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[170px]">Timestamp</TableHead>
                    <TableHead className="w-[90px]">Category</TableHead>
                    <TableHead className="w-[180px]">Action</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Target</TableHead>
                    <TableHead>Details</TableHead>
                    <TableHead className="w-[110px]">IP Address</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-10 text-slate-400">
                        <ScrollText className="h-10 w-10 mx-auto mb-3 opacity-30" />
                        No audit logs found
                      </TableCell>
                    </TableRow>
                  ) : (
                    logs.map((log: any, idx: number) => {
                      const details = parseDetails(log.details)
                      const detailStr =
                        typeof details === 'object' && details
                          ? Object.entries(details)
                              .filter(([k, v]) => v && k !== 'reason')
                              .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`)
                              .join(', ')
                          : String(details || '')
                      const reason = typeof details === 'object' && details?.reason ? details.reason : ''

                      return (
                        <TableRow key={log.record_id || idx}>
                          <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                            {formatTimestamp(log.created_date)}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              className={categoryColors[log.category] || 'bg-slate-100 text-slate-600'}
                            >
                              {log.category}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-medium text-sm">
                            {(log.action || '').replace(/_/g, ' ')}
                          </TableCell>
                          <TableCell className="text-sm">
                            <div>{log.actor_name || '-'}</div>
                            {log.actor_email && (
                              <div className="text-xs text-slate-400">{log.actor_email}</div>
                            )}
                          </TableCell>
                          <TableCell className="text-sm">
                            {log.target_type && (
                              <span className="text-slate-500">
                                {log.target_type}
                                {log.target_id ? `: ${log.target_id}` : ''}
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-xs text-slate-500 max-w-[250px] truncate" title={detailStr || reason}>
                            {reason || detailStr || '-'}
                          </TableCell>
                          <TableCell className="text-xs text-slate-400 font-mono">
                            {log.ip_address || '-'}
                          </TableCell>
                        </TableRow>
                      )
                    })
                  )}
                </TableBody>
              </Table>
            </ScrollArea>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t">
              <span className="text-sm text-slate-500">
                Page {page} of {totalPages} ({total} total)
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </PageWrapper>
  )
}
