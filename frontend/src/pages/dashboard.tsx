import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Link } from 'react-router-dom'
import { useDialogs } from '@/contexts/dialog-context'
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
  TrendingUp,
  Inbox,
} from 'lucide-react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

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

// RFP Table Component
interface RfpTableProps {
  rfps: any[]
  showActions?: boolean
  onSubmit?: (rfpId: string) => void
}

function RfpTable({ rfps, showActions = false, onSubmit }: RfpTableProps) {
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

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="text-slate-500 font-medium">RFP ID</TableHead>
          <TableHead className="text-slate-500 font-medium">Owner</TableHead>
          <TableHead className="text-slate-500 font-medium">Published</TableHead>
          <TableHead className="text-slate-500 font-medium">Deadline</TableHead>
          {showActions && <TableHead className="text-slate-500 font-medium">Match</TableHead>}
          <TableHead className="text-slate-500 font-medium">Status</TableHead>
          {showActions && <TableHead className="text-slate-500 font-medium text-right">Actions</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rfps.map((rfp, index) => (
          <TableRow key={rfp.RFP_ID || index} className="group">
            <TableCell>
              {rfp.Link ? (
                <a
                  href={rfp.Link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-red-600 hover:text-red-700 font-medium text-sm"
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
            {showActions && (
              <TableCell>
                {rfp.match_percentage && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700">
                    {rfp.match_percentage}
                  </span>
                )}
              </TableCell>
            )}
            <TableCell>
              <StatusBadge status={rfp.status || 'open'} />
            </TableCell>
            {showActions && (
              <TableCell className="text-right">
                <Button
                  size="sm"
                  onClick={() => onSubmit?.(rfp.RFP_ID)}
                  className="h-8 bg-red-600 hover:bg-red-700 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Send className="h-3.5 w-3.5 mr-1.5" />
                  Submit
                </Button>
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

// Main Dashboard Component
export default function DashboardPage() {
  const { openSubmitRfpDialog } = useDialogs()
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['dashboardData'],
    queryFn: api.getDashboardData,
  })

  const handleSyncPortal = async () => {
    try {
      await api.syncPortalData()
      toast.success('Portal data synced successfully')
      refetch()
    } catch (error: any) {
      toast.error(error.message || 'Failed to sync portal data')
    }
  }

  const handleSubmitRfp = (rfpId: string) => {
    openSubmitRfpDialog(rfpId)
  }

  const stats = data?.rfp || {}
  const companies = data?.unique_companies || []
  const companiesRfps = data?.companies_rfps || {}
  const lastRunTime = data?.automation?.last_run_time

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
              title="Downloaded RFPs"
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
              <div className="p-2 rounded-lg bg-red-50">
                <Building2 className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <CardTitle className="text-base font-semibold text-slate-800">
                  RFP Management
                </CardTitle>
                <p className="text-xs text-slate-500 mt-0.5">
                  Only today's and upcoming RFPs are displayed
                </p>
              </div>
            </div>
            <Button
              size="sm"
              onClick={handleSyncPortal}
              disabled={isRefetching}
              className="bg-red-600 hover:bg-red-700 h-9"
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
                          'data-[state=active]:text-red-600 data-[state=active]:bg-transparent',
                          'data-[state=active]:shadow-none rounded-none border-b-2 border-transparent',
                          'data-[state=active]:border-red-600 transition-all'
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
                              onSubmit={handleSubmitRfp}
                            />
                          </TabsContent>
                          <TabsContent value="submitted" className="mt-0">
                            <RfpTable rfps={companyRfps.submitted || []} />
                          </TabsContent>
                          <TabsContent value="draft" className="mt-0">
                            <RfpTable
                              rfps={companyRfps.saved_draft || []}
                              showActions
                              onSubmit={handleSubmitRfp}
                            />
                          </TabsContent>
                          <TabsContent value="declined" className="mt-0">
                            <RfpTable rfps={companyRfps.declined || []} />
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
    </PageWrapper>
  )
}
