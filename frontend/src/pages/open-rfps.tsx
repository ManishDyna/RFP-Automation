import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Eye,
  MailWarning,
  Search,
  RefreshCw,
  Send,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
  UserCheck,
} from 'lucide-react'
import { toast } from 'sonner'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { api } from '@/lib/api'
import { formatDateMDY } from '@/lib/utils'
import { useHasPermission } from '@/hooks/use-auth'
import { DelegateRfpDialog } from '@/components/dialogs/delegate-rfp-dialog'

type OpenRfp = {
  rfp_id: string
  company_name: string
  rfp_end_date: string
  owner_name: string
  email_sent_at: string
  email_status: string
  participated: string
  link: string
  total_recipients: number
  responded_count: number
  pending_count: number
}

function participatedBadgeVariant(p: string): 'success' | 'warning' | 'destructive' | 'info' | 'outline' {
  const v = (p || '').toLowerCase()
  if (v === 'submitted') return 'success'
  if (v === 'declined') return 'destructive'
  if (v === 'saved_draft') return 'info'
  if (v === 'open' || v === '') return 'warning'
  return 'outline'
}

function participatedLabel(p: string): string {
  const v = (p || '').toLowerCase()
  if (v === 'submitted') return 'Submitted'
  if (v === 'declined') return 'Declined'
  if (v === 'saved_draft') return 'Saved Draft'
  if (v === 'open') return 'Open'
  if (!v) return 'Open'
  return p
}

type SortKey = 'company_name' | 'participated' | null
type SortDir = 'asc' | 'desc'

export default function OpenRfpsPage() {
  const [search, setSearch] = useState('')
  const [companyFilter, setCompanyFilter] = useState<string>('__all__')
  const [participatedFilter, setParticipatedFilter] = useState<string>('__all__')
  const [sortKey, setSortKey] = useState<SortKey>(null)
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [openRfpId, setOpenRfpId] = useState<string | null>(null)

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['open-rfps'],
    queryFn: () => api.listOpenRfps(),
    staleTime: 60 * 1000,
  })

  const rfps: OpenRfp[] = data?.rfps ?? []

  // Unique company options for the dropdown
  const companyOptions = useMemo(() => {
    const seen = new Set<string>()
    for (const r of rfps) {
      const c = (r.company_name || '').trim()
      if (c) seen.add(c)
    }
    return Array.from(seen).sort((a, b) => a.localeCompare(b))
  }, [rfps])

  // Unique participated values present in current data (normalised)
  const participatedOptions = useMemo(() => {
    const seen = new Set<string>()
    for (const r of rfps) {
      const v = (r.participated || '').trim().toLowerCase() || 'open'
      seen.add(v)
    }
    return Array.from(seen).sort((a, b) => a.localeCompare(b))
  }, [rfps])

  const toggleSort = (key: Exclude<SortKey, null>) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    let out = rfps.filter((r) => {
      if (q) {
        const hit =
          r.rfp_id.toLowerCase().includes(q) ||
          (r.company_name || '').toLowerCase().includes(q) ||
          (r.owner_name || '').toLowerCase().includes(q)
        if (!hit) return false
      }
      if (companyFilter !== '__all__' && (r.company_name || '').trim() !== companyFilter) {
        return false
      }
      if (participatedFilter !== '__all__') {
        const v = (r.participated || '').trim().toLowerCase() || 'open'
        if (v !== participatedFilter) return false
      }
      return true
    })

    if (sortKey) {
      const dirMul = sortDir === 'asc' ? 1 : -1
      out = [...out].sort((a, b) => {
        const av = (
          sortKey === 'participated'
            ? participatedLabel(a.participated)
            : (a[sortKey] || '')
        ).toString().toLowerCase()
        const bv = (
          sortKey === 'participated'
            ? participatedLabel(b.participated)
            : (b[sortKey] || '')
        ).toString().toLowerCase()
        if (av < bv) return -1 * dirMul
        if (av > bv) return 1 * dirMul
        return 0
      })
    }

    return out
  }, [rfps, search, companyFilter, participatedFilter, sortKey, sortDir])

  const renderSortIcon = (key: Exclude<SortKey, null>) => {
    if (sortKey !== key) return <ArrowUpDown className="h-3.5 w-3.5 ml-1 opacity-40" />
    return sortDir === 'asc'
      ? <ArrowUp className="h-3.5 w-3.5 ml-1" />
      : <ArrowDown className="h-3.5 w-3.5 ml-1" />
  }

  return (
    <PageWrapper
      title="Open RFP"
      description="Track who has and hasn't responded to each RFP actionable card email, and send reminders to non-responders."
      actions={
        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      }
    >
      <Card>
        <CardContent className="p-4">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[240px] max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search by RFP ID, company, owner..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>

            <Select value={companyFilter} onValueChange={setCompanyFilter}>
              <SelectTrigger className="w-[220px]">
                <SelectValue placeholder="All companies" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All companies</SelectItem>
                {companyOptions.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={participatedFilter} onValueChange={setParticipatedFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All statuses</SelectItem>
                {participatedOptions.map((p) => (
                  <SelectItem key={p} value={p}>{participatedLabel(p)}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {(companyFilter !== '__all__' || participatedFilter !== '__all__' || sortKey) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setCompanyFilter('__all__')
                  setParticipatedFilter('__all__')
                  setSortKey(null)
                  setSortDir('asc')
                }}
              >
                Clear
              </Button>
            )}

            <div className="ml-auto text-sm text-slate-500">
              {filtered.length} of {rfps.length} RFP{rfps.length === 1 ? '' : 's'}
            </div>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center text-slate-500">
              <MailWarning className="h-10 w-10 mx-auto mb-3 text-slate-300" />
              <p className="font-medium">No RFPs found</p>
              <p className="text-sm mt-1">
                Only RFPs we've sent the actionable card for are listed here.
              </p>
            </div>
          ) : (
            <div className="rounded-md border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>RFP ID</TableHead>
                    <TableHead>
                      <button
                        type="button"
                        className="inline-flex items-center font-semibold text-muted-foreground hover:text-slate-900"
                        onClick={() => toggleSort('company_name')}
                      >
                        Company
                        {renderSortIcon('company_name')}
                      </button>
                    </TableHead>
                    <TableHead>End Date</TableHead>
                    <TableHead>Email Sent</TableHead>
                    <TableHead>
                      <button
                        type="button"
                        className="inline-flex items-center font-semibold text-muted-foreground hover:text-slate-900"
                        onClick={() => toggleSort('participated')}
                      >
                        Participated
                        {renderSortIcon('participated')}
                      </button>
                    </TableHead>
                    <TableHead>Responded</TableHead>
                    <TableHead>Pending</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((r) => (
                    <TableRow key={r.rfp_id}>
                      <TableCell className="font-medium">{r.rfp_id}</TableCell>
                      <TableCell>{r.company_name || '-'}</TableCell>
                      <TableCell>{formatDateMDY(r.rfp_end_date)}</TableCell>
                      <TableCell>{formatDateMDY(r.email_sent_at)}</TableCell>
                      <TableCell>
                        <Badge variant={participatedBadgeVariant(r.participated)}>
                          {participatedLabel(r.participated)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="text-emerald-700 font-medium">
                          {r.responded_count}
                        </span>
                        <span className="text-slate-400"> / {r.total_recipients}</span>
                      </TableCell>
                      <TableCell>
                        {r.pending_count > 0 ? (
                          <Badge variant="warning">
                            {r.pending_count}/{r.total_recipients}
                          </Badge>
                        ) : (
                          <Badge variant="success">
                            0/{r.total_recipients}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setOpenRfpId(r.rfp_id)}
                        >
                          <Eye className="h-4 w-4 mr-2" />
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <OpenRfpDetailModal
        rfpId={openRfpId}
        onClose={() => setOpenRfpId(null)}
      />
    </PageWrapper>
  )
}

function OpenRfpDetailModal({
  rfpId,
  onClose,
}: {
  rfpId: string | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const canRemind = useHasPermission('rfp.open.remind')
  const canDelegate = useHasPermission('rfp.open.delegate')

  const [delegateTarget, setDelegateTarget] = useState<{
    product: string
    email: string
    name: string
  } | null>(null)

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['open-rfp-status', rfpId],
    queryFn: () => api.getOpenRfpStatus(rfpId as string),
    enabled: !!rfpId,
  })

  const remindMutation = useMutation({
    mutationFn: (emails: string[]) =>
      api.remindOpenRfp(rfpId as string, emails),
    onSuccess: (result) => {
      const sent = result.reminded_count || 0
      const failed = (result.results || []).filter((r) => r.status === 'Failed').length
      const skipped = (result.results || []).filter((r) => r.status === 'Skipped').length
      if (sent > 0 && failed === 0 && skipped === 0) {
        toast.success(`Reminder sent to ${sent} recipient${sent === 1 ? '' : 's'}.`)
      } else {
        toast.message(
          `Reminder result: ${sent} sent, ${failed} failed, ${skipped} skipped.`
        )
      }
      refetch()
      queryClient.invalidateQueries({ queryKey: ['open-rfps'] })
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to send reminder.')
    },
  })

  const rfp = data?.rfp
  const rows = data?.rows ?? []
  const reminders = data?.reminders ?? []

  // Unique pending emails (for the bulk "Remind All Pending" button).
  // A row that's been delegated away is no longer remindable — exclude it
  // (its new recipient row will appear separately and be picked up here).
  const pendingEmails = useMemo(() => {
    const seen = new Set<string>()
    for (const r of rows) {
      if (r.status === 'pending' && !r.former && !r.delegated_to_email) {
        seen.add(r.email)
      }
    }
    return Array.from(seen)
  }, [rows])

  const respondedEmails = useMemo(() => {
    const seen = new Set<string>()
    for (const r of rows) {
      if (r.status === 'responded') seen.add(r.email)
    }
    return seen
  }, [rows])

  return (
    <Dialog open={!!rfpId} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MailWarning className="h-5 w-5" />
            Open RFP — {rfp?.rfp_id || rfpId}
          </DialogTitle>
          <DialogDescription>
            {rfp?.company_name ? `${rfp.company_name} · ` : ''}
            Due {formatDateMDY(rfp?.rfp_end_date || '')}
            {rfp?.email_sent_at ? ` · Email sent ${formatDateMDY(rfp.email_sent_at)}` : ''}
          </DialogDescription>
        </DialogHeader>

        <div className="overflow-y-auto pr-1 space-y-6">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <div className="text-sm">
                  <span className="text-emerald-700 font-medium">
                    {respondedEmails.size}
                  </span>{' '}
                  responded ·{' '}
                  <span className="text-amber-700 font-medium">
                    {pendingEmails.length}
                  </span>{' '}
                  pending
                </div>
                {canRemind && pendingEmails.length > 0 && (
                  <Button
                    size="sm"
                    onClick={() => remindMutation.mutate(pendingEmails)}
                    disabled={remindMutation.isPending}
                  >
                    {remindMutation.isPending ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4 mr-2" />
                    )}
                    Remind All Pending ({pendingEmails.length})
                  </Button>
                )}
              </div>

              <div className="rounded-md border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Product</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Results</TableHead>
                      <TableHead>Remarks</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Reminders</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center text-slate-500 py-8">
                          No team members configured for this RFP.
                        </TableCell>
                      </TableRow>
                    ) : (
                      rows.map((r, idx) => {
                        const isPending = r.status === 'pending'
                        const isDelegatedAway = !!r.delegated_to_email
                        return (
                          <TableRow key={`${r.email}-${r.product}-${idx}`}>
                            <TableCell className="font-medium">{r.product || '-'}</TableCell>
                            <TableCell>
                              {isDelegatedAway ? (
                                <div className="space-y-0.5">
                                  <div className="line-through text-slate-400 text-sm">
                                    {r.email}
                                  </div>
                                  {r.name && (
                                    <div className="text-xs text-slate-400 line-through">{r.name}</div>
                                  )}
                                  <div className="font-bold text-slate-900 text-sm">
                                    → Delegated to {r.delegated_to_email}
                                  </div>
                                  {r.delegated_to_name && (
                                    <div className="text-xs text-slate-600">{r.delegated_to_name}</div>
                                  )}
                                </div>
                              ) : (
                                <div>
                                  <div>{r.email}</div>
                                  {r.name && (
                                    <div className="text-xs text-slate-500">{r.name}</div>
                                  )}
                                  {r.delegated_from_email && (
                                    <div className="text-xs text-slate-500 italic mt-1">
                                      Delegated from {r.delegated_from_email}
                                    </div>
                                  )}
                                </div>
                              )}
                            </TableCell>
                            <TableCell className="max-w-xs">
                              {isPending ? (
                                <span className="text-slate-400">—</span>
                              ) : (
                                <div className="text-sm whitespace-pre-wrap break-words" title={r.results}>
                                  {r.results || '-'}
                                </div>
                              )}
                            </TableCell>
                            <TableCell className="max-w-xs">
                              {isPending ? (
                                <span className="text-slate-400">—</span>
                              ) : (
                                <div className="text-sm whitespace-pre-wrap break-words" title={r.remarks}>
                                  {r.remarks || '-'}
                                </div>
                              )}
                            </TableCell>
                            <TableCell>
                              {isDelegatedAway ? (
                                <Badge
                                  variant="outline"
                                  title={
                                    r.delegated_by || r.delegated_at
                                      ? `Delegated${r.delegated_by ? ` by ${r.delegated_by}` : ''}${r.delegated_at ? ` on ${r.delegated_at}` : ''}`
                                      : 'Delegated'
                                  }
                                >
                                  <UserCheck className="h-3 w-3 mr-1" />
                                  Delegated
                                </Badge>
                              ) : isPending ? (
                                <Badge variant="warning">
                                  <AlertCircle className="h-3 w-3 mr-1" />
                                  Pending
                                </Badge>
                              ) : (
                                <Badge variant="success">
                                  <CheckCircle2 className="h-3 w-3 mr-1" />
                                  Responded
                                </Badge>
                              )}
                              {r.former && (
                                <Badge variant="outline" className="ml-2">
                                  Former
                                </Badge>
                              )}
                              {!isPending && r.responded_at && (
                                <div className="text-xs text-slate-500 mt-1">
                                  {formatDateMDY(r.responded_at)}
                                </div>
                              )}
                            </TableCell>
                            <TableCell>
                              {r.reminder_count > 0 ? (
                                <div className="text-xs">
                                  <div>{r.reminder_count} sent</div>
                                  {r.last_reminder_at && (
                                    <div className="text-slate-500">
                                      Last: {formatDateMDY(r.last_reminder_at)}
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <span className="text-slate-400">—</span>
                              )}
                            </TableCell>
                            <TableCell className="text-right">
                              {isDelegatedAway ? (
                                <span className="text-slate-400">—</span>
                              ) : (
                                <div className="inline-flex items-center gap-2 justify-end">
                                  {canRemind && isPending && !r.former && (
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => remindMutation.mutate([r.email])}
                                      disabled={remindMutation.isPending}
                                    >
                                      {remindMutation.isPending ? (
                                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                      ) : (
                                        <Send className="h-4 w-4 mr-2" />
                                      )}
                                      Remind
                                    </Button>
                                  )}
                                  {canDelegate && isPending && !r.former && r.product && r.product !== '-' && (
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() =>
                                        setDelegateTarget({
                                          product: r.product,
                                          email: r.email,
                                          name: r.name || '',
                                        })
                                      }
                                    >
                                      <UserCheck className="h-4 w-4 mr-2" />
                                      Delegate
                                    </Button>
                                  )}
                                </div>
                              )}
                            </TableCell>
                          </TableRow>
                        )
                      })
                    )}
                  </TableBody>
                </Table>
              </div>

              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-slate-800">
                    Reminder History
                  </h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => refetch()}
                    disabled={isFetching}
                  >
                    <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
                    Refresh
                  </Button>
                </div>
                {reminders.length === 0 ? (
                  <div className="text-sm text-slate-500 py-6 text-center border rounded-md">
                    No reminders have been sent for this RFP yet.
                  </div>
                ) : (
                  <div className="rounded-md border overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Sent At</TableHead>
                          <TableHead>Recipient</TableHead>
                          <TableHead>Sent By</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Error</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {reminders.map((h, i) => (
                          <TableRow key={`${h.sent_at}-${h.recipient_email}-${i}`}>
                            <TableCell>{h.sent_at || '-'}</TableCell>
                            <TableCell>
                              <div className="text-sm">{h.recipient_email}</div>
                              {h.recipient_name && (
                                <div className="text-xs text-slate-500">{h.recipient_name}</div>
                              )}
                            </TableCell>
                            <TableCell>
                              <div className="text-sm">{h.sent_by_name || h.sent_by_email || '-'}</div>
                              {h.sent_by_name && h.sent_by_email && (
                                <div className="text-xs text-slate-500">{h.sent_by_email}</div>
                              )}
                            </TableCell>
                            <TableCell>
                              {h.status === 'Sent' ? (
                                <Badge variant="success">Sent</Badge>
                              ) : h.status === 'Failed' ? (
                                <Badge variant="destructive">Failed</Badge>
                              ) : (
                                <Badge variant="outline">{h.status || '-'}</Badge>
                              )}
                            </TableCell>
                            <TableCell className="max-w-xs truncate text-xs text-slate-500" title={h.error_message}>
                              {h.error_message || '-'}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </DialogContent>

      {delegateTarget && rfpId && (
        <DelegateRfpDialog
          open={!!delegateTarget}
          onOpenChange={(v) => { if (!v) setDelegateTarget(null) }}
          rfpId={rfpId}
          product={delegateTarget.product}
          currentEmail={delegateTarget.email}
          currentName={delegateTarget.name}
          onSuccess={() => {
            setDelegateTarget(null)
            refetch()
            queryClient.invalidateQueries({ queryKey: ['open-rfps'] })
          }}
        />
      )}
    </Dialog>
  )
}
