import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  Search,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
} from 'lucide-react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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

function StatusBadge({ status }: { status: string }) {
  const statusLower = status?.toLowerCase()
  if (statusLower === 'success' || statusLower === 'completed') {
    return (
      <Badge variant="success" className="gap-1">
        <CheckCircle2 className="h-3 w-3" />
        Success
      </Badge>
    )
  }
  if (statusLower === 'failed' || statusLower === 'error') {
    return (
      <Badge variant="destructive" className="gap-1">
        <XCircle className="h-3 w-3" />
        Failed
      </Badge>
    )
  }
  if (statusLower === 'running' || statusLower === 'in_progress') {
    return (
      <Badge variant="warning" className="gap-1">
        <Clock className="h-3 w-3" />
        Running
      </Badge>
    )
  }
  return <Badge variant="secondary">{status || 'Unknown'}</Badge>
}

export default function LogsPage() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [searchTerm, setSearchTerm] = useState('')

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['automationLogs', page, pageSize],
    queryFn: () => api.getAutomationLogs(page, pageSize),
  })

  const logs = data?.logs || []
  const totalLogs = data?.total || 0
  const totalPages = Math.ceil(totalLogs / pageSize)

  const filteredLogs = searchTerm
    ? logs.filter((log: any) =>
        Object.values(log).some((value) =>
          String(value).toLowerCase().includes(searchTerm.toLowerCase())
        )
      )
    : logs

  // Calculate stats from current page logs
  const successCount = filteredLogs.filter((l: any) =>
    ['success', 'completed'].includes(l.status?.toLowerCase())
  ).length
  const failedCount = filteredLogs.filter((l: any) =>
    ['failed', 'error'].includes(l.status?.toLowerCase())
  ).length
  const runningCount = filteredLogs.filter((l: any) =>
    ['running', 'in_progress'].includes(l.status?.toLowerCase())
  ).length

  return (
    <PageWrapper
      title="Activity Logs"
      description="Monitor automation events and track RFP processing history"
      actions={
        <Button
          variant="outline"
          onClick={() => refetch()}
          disabled={isRefetching}
          className="border-slate-200 hover:bg-slate-50"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isRefetching ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      }
    >
      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="rounded-xl p-4 stat-card-blue">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">Total Logs</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{totalLogs}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-white/60 flex items-center justify-center">
              <FileText className="h-5 w-5 text-slate-600" />
            </div>
          </div>
        </div>
        <div className="rounded-xl p-4 stat-card-emerald">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">Successful</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{successCount}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-white/60 flex items-center justify-center">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            </div>
          </div>
        </div>
        <div className="rounded-xl p-4 stat-card-rose">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">Failed</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{failedCount}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-white/60 flex items-center justify-center">
              <XCircle className="h-5 w-5 text-rose-600" />
            </div>
          </div>
        </div>
        <div className="rounded-xl p-4 stat-card-amber">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">Running</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{runningCount}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-white/60 flex items-center justify-center">
              <Clock className="h-5 w-5 text-amber-600" />
            </div>
          </div>
        </div>
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4 border-b border-slate-100 bg-slate-50/50">
          <CardTitle className="text-base font-semibold text-slate-800 flex items-center gap-2">
            <Activity className="h-5 w-5 text-indigo-600" />
            Event History
          </CardTitle>
          <div className="flex items-center gap-3">
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search logs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 bg-white border-slate-200"
              />
            </div>
            <Select
              value={String(pageSize)}
              onValueChange={(value) => {
                setPageSize(Number(value))
                setPage(1)
              }}
            >
              <SelectTrigger className="w-[100px] bg-white border-slate-200">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10 rows</SelectItem>
                <SelectItem value="20">20 rows</SelectItem>
                <SelectItem value="50">50 rows</SelectItem>
                <SelectItem value="100">100 rows</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex items-center gap-4">
                  <Skeleton className="h-10 w-20" />
                  <Skeleton className="h-10 w-32" />
                  <Skeleton className="h-10 w-24" />
                  <Skeleton className="h-10 flex-1" />
                  <Skeleton className="h-10 w-24" />
                </div>
              ))}
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-500">
              <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                <Activity className="h-8 w-8 text-slate-400" />
              </div>
              <p className="text-lg font-medium text-slate-600 mb-2">No logs found</p>
              <p className="text-sm text-slate-400 mb-4">
                {searchTerm ? 'Try adjusting your search term' : 'Automation logs will appear here'}
              </p>
              {searchTerm && (
                <Button variant="outline" onClick={() => setSearchTerm('')} className="border-slate-200">
                  Clear Search
                </Button>
              )}
            </div>
          ) : (
            <ScrollArea className="h-[520px]">
              <Table>
                <TableHeader className="sticky top-0 bg-slate-50/95 backdrop-blur-sm z-10">
                  <TableRow className="border-slate-200 hover:bg-slate-50/95">
                    <TableHead className="text-slate-600 font-semibold">Run ID</TableHead>
                    <TableHead className="text-slate-600 font-semibold">Event Time</TableHead>
                    <TableHead className="text-slate-600 font-semibold">Category</TableHead>
                    <TableHead className="text-slate-600 font-semibold">RFP ID</TableHead>
                    <TableHead className="text-slate-600 font-semibold">Action</TableHead>
                    <TableHead className="text-slate-600 font-semibold">Status</TableHead>
                    <TableHead className="text-slate-600 font-semibold max-w-[300px]">Details</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLogs.map((log: any, index: number) => (
                    <TableRow key={log.id || index} className="border-slate-100 hover:bg-slate-50/50 transition-colors">
                      <TableCell className="font-mono text-xs text-slate-500">
                        {log.run_id || '-'}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-sm text-slate-600">
                        {log.event_time || '-'}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs border-slate-200 text-slate-600">
                          {log.event_type || '-'}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium text-indigo-600">
                        {log.rfp_id || '-'}
                      </TableCell>
                      <TableCell className="text-sm text-slate-600">{log.action || '-'}</TableCell>
                      <TableCell>
                        <StatusBadge status={log.status} />
                      </TableCell>
                      <TableCell className="max-w-[300px] text-sm text-slate-500 truncate" title={log.details || ''}>
                        {log.details || '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          )}

          {/* Pagination */}
          {totalPages > 0 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50/50">
              <p className="text-sm text-slate-500">
                Showing <span className="font-semibold text-slate-700">{(page - 1) * pageSize + 1}</span> to{' '}
                <span className="font-semibold text-slate-700">{Math.min(page * pageSize, totalLogs)}</span> of{' '}
                <span className="font-semibold text-slate-700">{totalLogs}</span> logs
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="border-slate-200 hover:bg-slate-50"
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>
                <span className="text-sm text-slate-600 px-3 py-1 bg-white rounded-md border border-slate-200">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="border-slate-200 hover:bg-slate-50"
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </PageWrapper>
  )
}
