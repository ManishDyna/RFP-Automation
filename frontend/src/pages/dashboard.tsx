import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { useVirtualizer } from '@tanstack/react-virtual'
import { toast } from 'sonner'
import { Link } from 'react-router-dom'
import { useDialogs } from '@/contexts/dialog-context'
import { useRef, useState, useCallback, useEffect, useMemo } from 'react'
import {
  Download,
  CheckCircle2,
  XCircle,
  Clock,
  Building2,
  ExternalLink,
  Send,
  RefreshCw,
  ArrowUpRight,
  ArrowRight,
  FileText,
  FileSpreadsheet,
  TrendingUp,
  Inbox,
  ArrowRightLeft,
  Eye,
  BarChart3,
} from 'lucide-react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { Progress } from '@/components/ui/progress'
import { MaterialBreakdownDialog } from '@/components/dialogs/material-breakdown-dialog'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

// Threshold for enabling virtualization (only virtualize when > this many rows)
const VIRTUALIZATION_THRESHOLD = 50

// Metric Card Component
interface MetricCardProps {
  title: string
  value: string | number
  icon: React.ReactNode
  trend?: string
  trendUp?: boolean
  href?: string
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
}

function MetricCard({ title, value, icon, trend, trendUp, href, variant = 'default' }: MetricCardProps) {
  const variantStyles = {
    default: 'bg-slate-50 text-slate-600',
    success: 'bg-emerald-50 text-emerald-600',
    warning: 'bg-amber-50 text-amber-600',
    danger: 'bg-rose-50 text-rose-600',
    info: 'bg-sky-50 text-sky-600',
  }

  const content = (
    <Card className={cn(
      'relative overflow-hidden transition-all duration-200',
      'hover:shadow-md hover:border-slate-300',
      href && 'cursor-pointer group'
    )}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-500">{title}</p>
            <p className="text-2xl font-bold text-slate-900 tracking-tight">{value}</p>
            {trend && (
              <div className={cn(
                'inline-flex items-center gap-1 text-xs font-medium',
                trendUp ? 'text-emerald-600' : 'text-slate-500'
              )}>
                {trendUp && <TrendingUp className="h-3 w-3" />}
                {trend}
              </div>
            )}
          </div>
          <div className={cn('p-3 rounded-xl', variantStyles[variant])}>
            {icon}
          </div>
        </div>
        {href && (
          <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
            <ArrowUpRight className="h-4 w-4 text-slate-400" />
          </div>
        )}
      </CardContent>
    </Card>
  )

  if (href) {
    return <Link to={href} className="block">{content}</Link>
  }

  return content
}

function MetricCardSkeleton() {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-16" />
          </div>
          <Skeleton className="h-12 w-12 rounded-xl" />
        </div>
      </CardContent>
    </Card>
  )
}

// Status Badge Component
function StatusBadge({ status }: { status: string }) {
  const statusConfig: Record<string, { label: string; className: string }> = {
    open: {
      label: 'Open',
      className: 'bg-amber-50 text-amber-700 border-amber-200',
    },
    submitted: {
      label: 'Submitted',
      className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    },
    declined: {
      label: 'Declined',
      className: 'bg-rose-50 text-rose-700 border-rose-200',
    },
    'saved draft': {
      label: 'Draft',
      className: 'bg-slate-50 text-slate-700 border-slate-200',
    },
    draft: {
      label: 'Draft',
      className: 'bg-slate-50 text-slate-700 border-slate-200',
    },
  }

  const config = statusConfig[status?.toLowerCase()] || {
    label: status || 'Unknown',
    className: 'bg-slate-50 text-slate-700 border-slate-200',
  }

  return (
    <span className={cn(
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border',
      config.className
    )}>
      {config.label}
    </span>
  )
}

// Helper: get badge color for match percentage
function getMatchBadgeStyle(pct: number) {
  if (pct >= 80) return 'bg-emerald-100 text-emerald-700 border-emerald-200'
  if (pct >= 50) return 'bg-amber-100 text-amber-700 border-amber-200'
  if (pct > 0) return 'bg-rose-100 text-rose-700 border-rose-200'
  return 'bg-slate-100 text-slate-500 border-slate-200'
}

function getProgressBarColor(pct: number) {
  if (pct >= 80) return '[&>div]:bg-emerald-500'
  if (pct >= 50) return '[&>div]:bg-amber-500'
  return '[&>div]:bg-rose-500'
}

// RFP Table Row Component (extracted for virtualization)
interface RfpTableRowProps {
  rfp: any
  index: number
  showActions: boolean
  tableType: 'open' | 'draft'
  onSubmit?: (rfpId: string) => void
  onChangeStatus?: (rfpId: string, newStatus: string) => void
  onDownloadExcel?: (rfpId: string, company?: string) => void
  downloadingRfpId?: string | null
  matchData?: { match_percentage: number; total_materials: number; matched_count: number } | null
  onViewBreakdown?: (rfpId: string) => void
}

function RfpTableRow({ rfp, index, showActions, tableType, onSubmit, onChangeStatus, onDownloadExcel, downloadingRfpId, matchData, onViewBreakdown }: RfpTableRowProps) {
  const isDownloading = downloadingRfpId === rfp.RFP_ID
  const pct = matchData?.match_percentage ?? null
  return (
    <TableRow key={rfp.RFP_ID || index} className="group">
      <TableCell>
        {rfp.Link ? (
          <a
            href={rfp.Link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-indigo-600 hover:text-indigo-700 font-medium text-sm"
          >
            {rfp.RFP_ID}
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        ) : (
          <span className="font-medium text-slate-700 text-sm">{rfp.RFP_ID}</span>
        )}
      </TableCell>
      <TableCell className="text-slate-600 text-sm">{rfp.Owner_Name || '-'}</TableCell>
      <TableCell className="text-slate-500 text-sm">{rfp.Publish_Time || '-'}</TableCell>
      <TableCell className="text-slate-500 text-sm">{rfp.RFP_End_Date || '-'}</TableCell>
      <TableCell>
        {pct !== null ? (
          <div className="flex items-center gap-1.5">
            <span className={cn(
              'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border',
              getMatchBadgeStyle(pct)
            )}>
              <BarChart3 className="h-3 w-3" />
              {pct}%
            </span>
            <Progress value={pct} className={cn('h-1.5 w-12 bg-slate-200', getProgressBarColor(pct))} />
            <button
              onClick={() => onViewBreakdown?.(rfp.RFP_ID)}
              className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-slate-100"
              title="View material breakdown"
            >
              <Eye className="h-3.5 w-3.5 text-slate-400 hover:text-indigo-600" />
            </button>
          </div>
        ) : (
          <span className="text-xs text-slate-400">-</span>
        )}
      </TableCell>
      <TableCell>
        <StatusBadge status={rfp.status || 'open'} />
      </TableCell>
      <TableCell className="text-right">
        <div className="flex items-center justify-end gap-2">
          <Button
            size="sm"
            disabled={isDownloading}
            onClick={() => onDownloadExcel?.(rfp.RFP_ID, rfp.Company_Name)}
            className="h-8 bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            <FileSpreadsheet className={`h-3.5 w-3.5 mr-1.5 ${isDownloading ? 'animate-spin' : ''}`} />
            {isDownloading ? '...' : 'Excel'}
          </Button>
          {showActions && tableType === 'draft' && (
            <Button
              size="sm"
              onClick={() => onChangeStatus?.(rfp.RFP_ID, 'submitted')}
              className="h-8 bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              <ArrowRightLeft className="h-3.5 w-3.5 mr-1.5" />
              Mark Submitted
            </Button>
          )}
          {showActions && tableType === 'open' && (
            <Button
              size="sm"
              onClick={() => onSubmit?.(rfp.RFP_ID)}
              className="h-8 bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              <Send className="h-3.5 w-3.5 mr-1.5" />
              Submit
            </Button>
          )}
        </div>
      </TableCell>
    </TableRow>
  )
}

// RFP Table Component with virtualization for large datasets
interface RfpTableProps {
  rfps: any[]
  showActions?: boolean
  tableType?: 'open' | 'draft'
  onSubmit?: (rfpId: string) => void
  onChangeStatus?: (rfpId: string, newStatus: string) => void
  onDownloadExcel?: (rfpId: string, company?: string) => void
  downloadingRfpId?: string | null
  matchPercentages?: Record<string, { match_percentage: number; total_materials: number; matched_count: number }>
  onViewBreakdown?: (rfpId: string) => void
}

function RfpTable({ rfps, showActions = false, tableType = 'open', onSubmit, onChangeStatus, onDownloadExcel, downloadingRfpId, matchPercentages = {}, onViewBreakdown }: RfpTableProps) {
  const parentRef = useRef<HTMLDivElement>(null)

  // Use virtualization only for large datasets
  const useVirtual = rfps && rfps.length > VIRTUALIZATION_THRESHOLD

  const rowVirtualizer = useVirtualizer({
    count: rfps?.length || 0,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52, // Estimated row height in pixels
    overscan: 10, // Render extra rows above/below visible area for smooth scrolling
    enabled: useVirtual,
  })

  if (!rfps || rfps.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center mb-4">
          <Inbox className="h-7 w-7 text-slate-400" />
        </div>
        <p className="text-sm font-medium text-slate-600 mb-1">No RFPs found</p>
        <p className="text-xs text-slate-400">RFPs will appear here once available</p>
      </div>
    )
  }

  // Regular table for small datasets (no virtualization overhead)
  if (!useVirtual) {
    return (
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="text-slate-500 font-medium">RFP ID</TableHead>
            <TableHead className="text-slate-500 font-medium">Owner</TableHead>
            <TableHead className="text-slate-500 font-medium">Published</TableHead>
            <TableHead className="text-slate-500 font-medium">Deadline</TableHead>
            <TableHead className="text-slate-500 font-medium">Match %</TableHead>
            <TableHead className="text-slate-500 font-medium">Status</TableHead>
            <TableHead className="text-slate-500 font-medium text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rfps.map((rfp, index) => (
            <RfpTableRow
              key={rfp.RFP_ID || index}
              rfp={rfp}
              index={index}
              showActions={showActions}
              tableType={tableType}
              onSubmit={onSubmit}
              onChangeStatus={onChangeStatus}
              onDownloadExcel={onDownloadExcel}
              downloadingRfpId={downloadingRfpId}
              matchData={matchPercentages[rfp.RFP_ID] || null}
              onViewBreakdown={onViewBreakdown}
            />
          ))}
        </TableBody>
      </Table>
    )
  }

  // Virtualized table for large datasets (50+ rows)
  return (
    <div>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="text-slate-500 font-medium">RFP ID</TableHead>
            <TableHead className="text-slate-500 font-medium">Owner</TableHead>
            <TableHead className="text-slate-500 font-medium">Published</TableHead>
            <TableHead className="text-slate-500 font-medium">Deadline</TableHead>
            <TableHead className="text-slate-500 font-medium">Match %</TableHead>
            <TableHead className="text-slate-500 font-medium">Status</TableHead>
            <TableHead className="text-slate-500 font-medium text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
      </Table>
      <div
        ref={parentRef}
        className="overflow-auto"
        style={{ height: '400px' }} // Fixed height for virtualization
      >
        <div
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          <Table>
            <TableBody>
              {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                const rfp = rfps[virtualRow.index]
                const isDownloading = downloadingRfpId === rfp.RFP_ID
                const pctData = matchPercentages[rfp.RFP_ID]
                const pct = pctData?.match_percentage ?? null
                return (
                  <TableRow
                    key={rfp.RFP_ID || virtualRow.index}
                    className="group"
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: `${virtualRow.size}px`,
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    <TableCell>
                      {rfp.Link ? (
                        <a
                          href={rfp.Link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-indigo-600 hover:text-indigo-700 font-medium text-sm"
                        >
                          {rfp.RFP_ID}
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      ) : (
                        <span className="font-medium text-slate-700 text-sm">{rfp.RFP_ID}</span>
                      )}
                    </TableCell>
                    <TableCell className="text-slate-600 text-sm">{rfp.Owner_Name || '-'}</TableCell>
                    <TableCell className="text-slate-500 text-sm">{rfp.Publish_Time || '-'}</TableCell>
                    <TableCell className="text-slate-500 text-sm">{rfp.RFP_End_Date || '-'}</TableCell>
                    <TableCell>
                      {pct !== null ? (
                        <div className="flex items-center gap-1.5">
                          <span className={cn(
                            'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border',
                            getMatchBadgeStyle(pct)
                          )}>
                            <BarChart3 className="h-3 w-3" />
                            {pct}%
                          </span>
                          <Progress value={pct} className={cn('h-1.5 w-12 bg-slate-200', getProgressBarColor(pct))} />
                          <button
                            onClick={() => onViewBreakdown?.(rfp.RFP_ID)}
                            className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-slate-100"
                            title="View material breakdown"
                          >
                            <Eye className="h-3.5 w-3.5 text-slate-400 hover:text-indigo-600" />
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={rfp.status || 'open'} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          size="sm"
                          disabled={isDownloading}
                          onClick={() => onDownloadExcel?.(rfp.RFP_ID, rfp.Company_Name)}
                          className="h-8 bg-emerald-600 hover:bg-emerald-700 text-white"
                        >
                          <FileSpreadsheet className={`h-3.5 w-3.5 mr-1.5 ${isDownloading ? 'animate-spin' : ''}`} />
                          {isDownloading ? '...' : 'Excel'}
                        </Button>
                        {showActions && tableType === 'draft' && (
                          <Button
                            size="sm"
                            onClick={() => onChangeStatus?.(rfp.RFP_ID, 'submitted')}
                            className="h-8 bg-indigo-600 hover:bg-indigo-700 text-white"
                          >
                            <ArrowRightLeft className="h-3.5 w-3.5 mr-1.5" />
                            Mark Submitted
                          </Button>
                        )}
                        {showActions && tableType === 'open' && (
                          <Button
                            size="sm"
                            onClick={() => onSubmit?.(rfp.RFP_ID)}
                            className="h-8 bg-indigo-600 hover:bg-indigo-700 text-white"
                          >
                            <Send className="h-3.5 w-3.5 mr-1.5" />
                            Submit
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      </div>
      <div className="text-xs text-slate-400 mt-2 text-center">
        Showing {rfps.length} rows (virtualized for performance)
      </div>
    </div>
  )
}

// Main Dashboard Component
export default function DashboardPage() {
  const { openSubmitRfpDialog } = useDialogs()
  const queryClient = useQueryClient()
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['dashboardData'],
    queryFn: api.getDashboardData,
  })

  // Optimistic mutation for instant status updates
  const statusMutation = useMutation({
    mutationFn: ({ rfpId, newStatus }: { rfpId: string; newStatus: string }) =>
      api.updateRfpStatus(rfpId, newStatus),
    onMutate: async ({ rfpId, newStatus }) => {
      // Cancel any outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ['dashboardData'] })

      // Snapshot the previous value
      const previousData = queryClient.getQueryData(['dashboardData'])

      // Optimistically update the cache
      queryClient.setQueryData(['dashboardData'], (old: any) => {
        if (!old?.companies_rfps) return old

        const updated = { ...old, companies_rfps: { ...old.companies_rfps } }

        // Find and move the RFP from its current status to the new status
        for (const company in updated.companies_rfps) {
          const companyData = { ...updated.companies_rfps[company] }
          updated.companies_rfps[company] = companyData

          // Check saved_draft (source for "Mark Submitted")
          if (companyData.saved_draft) {
            const rfpIndex = companyData.saved_draft.findIndex((r: any) => r.RFP_ID === rfpId)
            if (rfpIndex !== -1) {
              const [rfp] = companyData.saved_draft.splice(rfpIndex, 1)
              companyData.saved_draft = [...companyData.saved_draft]
              rfp.status = newStatus
              rfp.participated = newStatus

              // Add to new status array
              if (!companyData[newStatus]) companyData[newStatus] = []
              companyData[newStatus] = [...companyData[newStatus], rfp]
              break
            }
          }
        }

        return updated
      })

      return { previousData }
    },
    onError: (err: any, variables, context) => {
      // Rollback on error
      if (context?.previousData) {
        queryClient.setQueryData(['dashboardData'], context.previousData)
      }
      toast.error(err.message || 'Failed to update RFP status')
    },
    onSuccess: (_, { rfpId, newStatus }) => {
      toast.success(`RFP ${rfpId} status changed to ${newStatus}`)
    },
    onSettled: () => {
      // Refetch in background to ensure server consistency
      queryClient.invalidateQueries({ queryKey: ['dashboardData'] })
    },
  })

  const [downloadingRfpId, setDownloadingRfpId] = useState<string | null>(null)

  // Match percentage data (loaded via batch endpoint)
  const [matchPercentages, setMatchPercentages] = useState<Record<string, { match_percentage: number; total_materials: number; matched_count: number }>>({})

  // Material Breakdown Dialog state
  const [breakdownDialogOpen, setBreakdownDialogOpen] = useState(false)
  const [breakdownRfpId, setBreakdownRfpId] = useState<string | null>(null)
  const [breakdownCompany, setBreakdownCompany] = useState<string | null>(null)

  const handleDownloadExcel = useCallback(async (rfpId: string, company?: string) => {
    setDownloadingRfpId(rfpId)
    try {
      await api.downloadExcel(rfpId, company)
      toast.success(`Excel downloaded for ${rfpId}`)
    } catch (error: any) {
      toast.error(error.message || 'Failed to download Excel file')
    } finally {
      setDownloadingRfpId(null)
    }
  }, [])

  const handleSyncPortal = async () => {
    try {
      // Collect all RFP IDs currently visible in the dashboard (today's and future RFPs)
      const dashboardRfpIds: string[] = []
      for (const company of companies) {
        const companyRfps = companiesRfps[company] || {}
        for (const status of ['open', 'submitted', 'saved_draft', 'declined']) {
          const rfps = companyRfps[status] || []
          for (const rfp of rfps) {
            if (rfp.RFP_ID && !dashboardRfpIds.includes(rfp.RFP_ID)) {
              dashboardRfpIds.push(rfp.RFP_ID)
            }
          }
        }
      }
      await api.syncPortalData(dashboardRfpIds.length > 0 ? dashboardRfpIds : undefined)
      toast.success('Portal data synced successfully')
      refetch()
    } catch (error: any) {
      toast.error(error.message || 'Failed to sync portal data')
    }
  }

  const handleSubmitRfp = (rfpId: string) => {
    openSubmitRfpDialog(rfpId)
  }

  const handleChangeStatus = (rfpId: string, newStatus: string) => {
    statusMutation.mutate({ rfpId, newStatus })
  }

  const stats = data?.rfp || {}
  const companies = data?.unique_companies || []
  const companiesRfps = data?.companies_rfps || {}
  const lastRunTime = data?.automation?.last_run_time

  // Collect all RFP IDs and their company mappings for batch fetch
  const { allRfpIds, rfpCompanyMap } = useMemo(() => {
    const ids: string[] = []
    const companyMap: Record<string, string> = {}
    for (const company of companies) {
      const compRfps = companiesRfps[company] || {}
      for (const status of ['open', 'submitted', 'saved_draft', 'declined']) {
        const rfps = compRfps[status] || []
        for (const rfp of rfps) {
          if (rfp.RFP_ID && !ids.includes(rfp.RFP_ID)) {
            ids.push(rfp.RFP_ID)
            companyMap[rfp.RFP_ID] = company
          }
        }
      }
    }
    return { allRfpIds: ids, rfpCompanyMap: companyMap }
  }, [companies, companiesRfps])

  // Fetch match percentages from batch endpoint
  useEffect(() => {
    if (allRfpIds.length === 0) return

    const needsFetch = allRfpIds.filter((id) => !matchPercentages[id])
    if (needsFetch.length === 0) return

    // Build company map for only the IDs we need to fetch
    const companiesForFetch: Record<string, string> = {}
    for (const id of needsFetch) {
      if (rfpCompanyMap[id]) {
        companiesForFetch[id] = rfpCompanyMap[id]
      }
    }

    api.getBatchMatchPercentages(needsFetch, companiesForFetch)
      .then((result) => {
        setMatchPercentages((prev) => ({ ...prev, ...result }))
      })
      .catch((err) => {
        console.error('Failed to fetch match percentages:', err)
      })
  }, [allRfpIds.length])

  const handleViewBreakdown = useCallback((rfpId: string, company?: string) => {
    setBreakdownRfpId(rfpId)
    setBreakdownCompany(company || rfpCompanyMap[rfpId] || null)
    setBreakdownDialogOpen(true)
  }, [rfpCompanyMap])

  // Format last run time
  const formatLastRun = (time: string) => {
    if (!time || time === '-') return 'Never'
    return time
  }

  return (
    <PageWrapper
      title="Dashboard"
      description="Monitor your RFP automation activity and manage submissions"
      actions={
        <Link to="/dashboard/rfp-insights">
          <Button variant="outline" className="border-slate-200 hover:bg-slate-50">
            <FileText className="h-4 w-4 mr-2" />
            View All RFPs
            <ArrowRight className="h-4 w-4 ml-2" />
          </Button>
        </Link>
      }
    >
      {/* Metrics Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        {isLoading ? (
          <>
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
          </>
        ) : (
          <>
            <MetricCard
              title="Total Downloaded RFPs"
              value={stats.downloaded_rfps || 0}
              icon={<Download className="h-5 w-5" />}
              variant="warning"
              href="/dashboard/rfp-insights?status=downloaded"
            />
            <MetricCard
              title="Submitted"
              value={data?.total_submitted_rfps || 0}
              icon={<CheckCircle2 className="h-5 w-5" />}
              variant="success"
              href="/dashboard/rfp-insights?status=submitted"
            />
            <MetricCard
              title="Declined"
              value={data?.total_declined_rfps || 0}
              icon={<XCircle className="h-5 w-5" />}
              variant="danger"
              href="/dashboard/rfp-insights?status=declined"
            />
            <MetricCard
              title="Last Automation"
              value={formatLastRun(lastRunTime)}
              icon={<Clock className="h-5 w-5" />}
              variant="info"
            />
          </>
        )}
      </div>

      {/* RFP Management Section */}
      <Card className="border-slate-200">
        <CardHeader className="border-b border-slate-100 bg-slate-50/50">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-indigo-50">
                <Building2 className="h-5 w-5 text-indigo-600" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold text-slate-800">
                  RFP Management
                </CardTitle>
                <p className="text-xs text-slate-500 mt-0.5">
                  RFPs with passed deadlines are hidden
                </p>
              </div>
            </div>
            <Button
              size="sm"
              onClick={handleSyncPortal}
              disabled={isRefetching}
              className="bg-indigo-600 hover:bg-indigo-700 h-9"
            >
              <RefreshCw className={cn('h-4 w-4 mr-2', isRefetching && 'animate-spin')} />
              Sync Portal
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-64 w-full" />
            </div>
          ) : companies.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                <Building2 className="h-8 w-8 text-slate-400" />
              </div>
              <p className="text-sm font-medium text-slate-600 mb-1">No companies found</p>
              <p className="text-xs text-slate-400 mb-4">Sync with portal to load companies</p>
              <Button size="sm" variant="outline" onClick={handleSyncPortal}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Sync Now
              </Button>
            </div>
          ) : (
            <Tabs defaultValue={companies[0]} className="w-full">
              {/* Company Tabs */}
              <div className="border-b border-slate-100 px-4">
                <TabsList className="h-auto p-0 bg-transparent gap-0">
                  {companies.map((company: string) => {
                    const companyRfps = companiesRfps[company] || {}
                    const total =
                      (companyRfps.open?.length || 0) +
                      (companyRfps.submitted?.length || 0) +
                      (companyRfps.saved_draft?.length || 0) +
                      (companyRfps.declined?.length || 0)
                    return (
                      <TabsTrigger
                        key={company}
                        value={company}
                        className={cn(
                          'relative px-4 py-3 text-sm font-medium text-slate-500',
                          'data-[state=active]:text-indigo-600 data-[state=active]:bg-transparent',
                          'data-[state=active]:shadow-none rounded-none border-b-2 border-transparent',
                          'data-[state=active]:border-indigo-600 transition-all'
                        )}
                      >
                        <Building2 className="h-4 w-4 mr-2 inline" />
                        {company}
                        <Badge
                          variant="secondary"
                          className="ml-2 bg-slate-100 text-slate-600 hover:bg-slate-100"
                        >
                          {total}
                        </Badge>
                      </TabsTrigger>
                    )
                  })}
                </TabsList>
              </div>

              {/* Company Content */}
              {companies.map((company: string) => {
                const companyRfps = companiesRfps[company] || {}
                return (
                  <TabsContent key={company} value={company} className="mt-0">
                    <Tabs defaultValue="open">
                      {/* Status Tabs */}
                      <div className="px-4 pt-4">
                        <TabsList className="bg-slate-100/70 p-1 h-auto">
                          <TabsTrigger
                            value="open"
                            className="text-xs data-[state=active]:bg-white data-[state=active]:shadow-sm px-3 py-1.5"
                          >
                            Open
                            <span className="ml-1.5 px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-[10px] font-semibold">
                              {companyRfps.open?.length || 0}
                            </span>
                          </TabsTrigger>
                          <TabsTrigger
                            value="submitted"
                            className="text-xs data-[state=active]:bg-white data-[state=active]:shadow-sm px-3 py-1.5"
                          >
                            Submitted
                            <span className="ml-1.5 px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 text-[10px] font-semibold">
                              {companyRfps.submitted?.length || 0}
                            </span>
                          </TabsTrigger>
                          <TabsTrigger
                            value="draft"
                            className="text-xs data-[state=active]:bg-white data-[state=active]:shadow-sm px-3 py-1.5"
                          >
                            Draft
                            <span className="ml-1.5 px-1.5 py-0.5 rounded bg-slate-200 text-slate-600 text-[10px] font-semibold">
                              {companyRfps.saved_draft?.length || 0}
                            </span>
                          </TabsTrigger>
                          <TabsTrigger
                            value="declined"
                            className="text-xs data-[state=active]:bg-white data-[state=active]:shadow-sm px-3 py-1.5"
                          >
                            Declined
                            <span className="ml-1.5 px-1.5 py-0.5 rounded bg-rose-100 text-rose-700 text-[10px] font-semibold">
                              {companyRfps.declined?.length || 0}
                            </span>
                          </TabsTrigger>
                        </TabsList>
                      </div>

                      {/* Table Content */}
                      <ScrollArea className="h-[400px]">
                        <div className="p-4">
                          <TabsContent value="open" className="mt-0">
                            <RfpTable
                              rfps={companyRfps.open || []}
                              showActions
                              tableType="open"
                              onSubmit={handleSubmitRfp}
                              onDownloadExcel={handleDownloadExcel}
                              downloadingRfpId={downloadingRfpId}
                              matchPercentages={matchPercentages}
                              onViewBreakdown={handleViewBreakdown}
                            />
                          </TabsContent>
                          <TabsContent value="submitted" className="mt-0">
                            <RfpTable
                              rfps={companyRfps.submitted || []}
                              onDownloadExcel={handleDownloadExcel}
                              downloadingRfpId={downloadingRfpId}
                              matchPercentages={matchPercentages}
                              onViewBreakdown={handleViewBreakdown}
                            />
                          </TabsContent>
                          <TabsContent value="draft" className="mt-0">
                            <RfpTable
                              rfps={companyRfps.saved_draft || []}
                              showActions
                              tableType="draft"
                              onChangeStatus={handleChangeStatus}
                              onDownloadExcel={handleDownloadExcel}
                              downloadingRfpId={downloadingRfpId}
                              matchPercentages={matchPercentages}
                              onViewBreakdown={handleViewBreakdown}
                            />
                          </TabsContent>
                          <TabsContent value="declined" className="mt-0">
                            <RfpTable
                              rfps={companyRfps.declined || []}
                              onDownloadExcel={handleDownloadExcel}
                              downloadingRfpId={downloadingRfpId}
                              matchPercentages={matchPercentages}
                              onViewBreakdown={handleViewBreakdown}
                            />
                          </TabsContent>
                        </div>
                      </ScrollArea>
                    </Tabs>
                  </TabsContent>
                )
              })}
            </Tabs>
          )}
        </CardContent>
      </Card>

      {/* Material Breakdown Dialog */}
      <MaterialBreakdownDialog
        open={breakdownDialogOpen}
        onOpenChange={setBreakdownDialogOpen}
        rfpId={breakdownRfpId}
        company={breakdownCompany}
      />
    </PageWrapper>
  )
}
