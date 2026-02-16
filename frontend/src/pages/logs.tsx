import { useState, useMemo } from 'react'
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
  Eye,
  AlertTriangle,
  ArrowRight,
  Filter,
  Loader2,
  Image,
  FileWarning,
  ChevronDown,
  ChevronUp,
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
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api } from '@/lib/api'
import { ENDPOINTS } from '@/lib/endpoints'

// ─── Types ───────────────────────────────────────────────────────

interface LogEntry {
  id: string
  run_id: string
  event_time: string
  event_type: string
  rfp_id: string
  action: string
  status: string
  details: string
}

interface AutomationRun {
  run_id: string
  rfp_id: string
  category: string
  action: string
  start_time: string
  end_time: string
  overall_status: 'completed' | 'failed' | 'running' | 'warning' | 'unknown'
  total_steps: number
  success_steps: number
  failed_steps: number
  warning_steps: number
  logs: LogEntry[]
}

interface ErrorFile {
  filename: string
  size: number
  modified: number
  type: string
}

// ─── Helpers ─────────────────────────────────────────────────────

// Patterns in messages that indicate a real failure even if status says "Warning"
const FAILURE_MESSAGE_PATTERNS = [
  'not found', 'not clickable', 'timeout', 'timed out', 'exception',
  'could not', 'unable to', 'cannot', 'crash', 'unexpected error',
]

function deriveOverallStatus(logs: LogEntry[]): AutomationRun['overall_status'] {
  const statuses = logs.map((l) => l.status?.toLowerCase())
  const lastStatus = statuses[statuses.length - 1]

  // 1. Explicit failure status in any step → failed
  if (statuses.some((s) => ['failed', 'error'].includes(s))) return 'failed'

  // 2. Warning steps with failure-indicating messages → failed
  const hasFailureMessage = logs.some((log) => {
    const msg = (log.details || '').toLowerCase()
    const s = log.status?.toLowerCase()
    return (s === 'warning' || s === 'error') &&
      FAILURE_MESSAGE_PATTERNS.some((pattern) => msg.includes(pattern))
  })

  // 3. Check if the run actually reached a proper completion step
  const completionStatuses = ['complete', 'completed']
  const hasCompletionStep = statuses.some((s) => completionStatuses.includes(s))
  const lastIsTerminal = ['complete', 'completed', 'success', 'skip'].includes(lastStatus)

  // 4. If run has in-progress steps but no completion → still running
  const inProgressStatuses = ['running', 'in_progress', 'downloading', 'uploading', 'navigating', 'clicking', 'saving', 'processing']
  if (statuses.some((s) => inProgressStatuses.includes(s)) && !hasCompletionStep && !hasFailureMessage) {
    return 'running'
  }

  // 5. If there are failure-indicating messages and no proper completion → failed
  if (hasFailureMessage && !hasCompletionStep) return 'failed'

  // 6. If the run has warnings with failure messages but DID complete → warning (it recovered)
  if (hasFailureMessage && hasCompletionStep) return 'warning'

  // 7. Only "skip" entries with no completion → completed (already processed)
  if (statuses.every((s) => s === 'skip')) return 'completed'

  // 8. Has proper completion step → completed
  if (hasCompletionStep || lastIsTerminal) return 'completed'

  // 9. Fallback: if last step is not terminal and there are steps, likely incomplete → failed
  if (logs.length > 0 && !lastIsTerminal) return 'failed'

  return 'unknown'
}

function groupLogsByRunId(logs: LogEntry[]): AutomationRun[] {
  const groups: Record<string, LogEntry[]> = {}

  for (const log of logs) {
    const key = log.run_id || 'unknown'
    if (!groups[key]) groups[key] = []
    groups[key].push(log)
  }

  return Object.entries(groups).map(([runId, entries]) => {
    // Sort entries by time ascending
    const sorted = [...entries].sort((a, b) => {
      const tA = a.event_time ? new Date(a.event_time).getTime() : 0
      const tB = b.event_time ? new Date(b.event_time).getTime() : 0
      return tA - tB
    })

    const statuses = sorted.map((l) => l.status?.toLowerCase())

    return {
      run_id: runId,
      rfp_id: sorted[0]?.rfp_id || '-',
      category: sorted[0]?.event_type || '-',
      action: [...new Set(sorted.map((l) => l.action))].filter(a => a !== '-').join(', ') || '-',
      start_time: sorted[0]?.event_time || '-',
      end_time: sorted[sorted.length - 1]?.event_time || '-',
      overall_status: deriveOverallStatus(sorted),
      total_steps: sorted.length,
      success_steps: statuses.filter((s) => ['success', 'complete', 'completed'].includes(s)).length,
      failed_steps: statuses.filter((s) => ['failed', 'error'].includes(s)).length,
      warning_steps: statuses.filter((s) => s === 'warning').length,
      logs: sorted,
    }
  }).sort((a, b) => {
    const tA = a.end_time !== '-' ? new Date(a.end_time).getTime() : 0
    const tB = b.end_time !== '-' ? new Date(b.end_time).getTime() : 0
    return tB - tA
  })
}

function formatShortTime(t: string) {
  if (!t || t === '-') return '-'
  try {
    const d = new Date(t)
    return d.toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: true,
    })
  } catch {
    return t
  }
}

// ─── Status Components ───────────────────────────────────────────

function StatusIcon({ status }: { status: AutomationRun['overall_status'] }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-5 w-5 text-emerald-500" />
    case 'failed':
      return <XCircle className="h-5 w-5 text-rose-500" />
    case 'running':
      return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
    case 'warning':
      return <AlertTriangle className="h-5 w-5 text-amber-500" />
    default:
      return <Clock className="h-5 w-5 text-slate-400" />
  }
}

function StatusBadge({ status }: { status: AutomationRun['overall_status'] }) {
  const config: Record<string, { variant: any; label: string }> = {
    completed: { variant: 'success', label: 'Completed' },
    failed: { variant: 'destructive', label: 'Failed' },
    running: { variant: 'info', label: 'Running' },
    warning: { variant: 'warning', label: 'Warning' },
    unknown: { variant: 'secondary', label: 'Unknown' },
  }
  const { variant, label } = config[status] || config.unknown
  return <Badge variant={variant}>{label}</Badge>
}

function StepStatusDot({ status }: { status: string }) {
  const s = status?.toLowerCase()
  if (['success', 'complete', 'completed'].includes(s))
    return <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
  if (['failed', 'error'].includes(s))
    return <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shrink-0" />
  if (s === 'warning')
    return <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0" />
  if (['skip'].includes(s))
    return <span className="w-2.5 h-2.5 rounded-full bg-slate-300 shrink-0" />
  return <span className="w-2.5 h-2.5 rounded-full bg-blue-400 shrink-0" />
}

// ─── Run Detail Modal ────────────────────────────────────────────

function RunDetailModal({
  run,
  open,
  onClose,
}: {
  run: AutomationRun | null
  open: boolean
  onClose: () => void
}) {
  const [activeTab, setActiveTab] = useState('timeline')

  // Fetch error files for this RFP
  const { data: errorFilesData, isLoading: loadingFiles } = useQuery({
    queryKey: ['errorFiles', run?.rfp_id],
    queryFn: () => api.getErrorFiles(run?.rfp_id),
    enabled: open && !!run && run.rfp_id !== '-',
  })

  const errorFiles = errorFilesData?.files || []
  const txtFiles = errorFiles.filter((f: ErrorFile) => f.type === 'report')
  const jsonFiles = errorFiles.filter((f: ErrorFile) => f.type === 'json')
  const screenshotFiles = errorFiles.filter((f: ErrorFile) => f.type === 'screenshot')
  const hasErrorData = txtFiles.length > 0 || jsonFiles.length > 0 || screenshotFiles.length > 0

  if (!run) return null

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] p-0 gap-0 overflow-hidden">
        {/* Header */}
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <DialogTitle className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                <StatusIcon status={run.overall_status} />
                Automation Details
              </DialogTitle>
              <DialogDescription className="mt-1.5 text-sm text-slate-500">
                Run ID: {run.run_id.substring(0, 8)}... | RFP: {run.rfp_id}
              </DialogDescription>
            </div>
            <StatusBadge status={run.overall_status} />
          </div>

          {/* Run summary bar */}
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-white rounded-lg border border-slate-100 p-2.5 text-center">
              <p className="text-xs text-slate-500">Action</p>
              <p className="text-sm font-semibold text-slate-800 truncate">{run.action}</p>
            </div>
            <div className="bg-white rounded-lg border border-slate-100 p-2.5 text-center">
              <p className="text-xs text-slate-500">Total Steps</p>
              <p className="text-sm font-semibold text-slate-800">{run.total_steps}</p>
            </div>
            <div className="bg-white rounded-lg border border-slate-100 p-2.5 text-center">
              <p className="text-xs text-slate-500">Start</p>
              <p className="text-sm font-semibold text-slate-800">{formatShortTime(run.start_time)}</p>
            </div>
            <div className="bg-white rounded-lg border border-slate-100 p-2.5 text-center">
              <p className="text-xs text-slate-500">End</p>
              <p className="text-sm font-semibold text-slate-800">{formatShortTime(run.end_time)}</p>
            </div>
          </div>
        </DialogHeader>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col flex-1 min-h-0">
          <div className="px-6 pt-3 border-b border-slate-100 bg-slate-50/50">
            <TabsList className="bg-transparent gap-1 p-0 h-auto">
              <TabsTrigger
                value="timeline"
                className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-t-lg rounded-b-none border-b-2 data-[state=active]:border-indigo-500 border-transparent px-4 py-2"
              >
                <Activity className="h-4 w-4 mr-1.5" />
                Process Timeline
              </TabsTrigger>
              {hasErrorData && (
                <TabsTrigger
                  value="error-report"
                  className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-t-lg rounded-b-none border-b-2 data-[state=active]:border-rose-500 border-transparent px-4 py-2"
                >
                  <FileWarning className="h-4 w-4 mr-1.5" />
                  Error Report
                </TabsTrigger>
              )}
              {screenshotFiles.length > 0 && (
                <TabsTrigger
                  value="screenshots"
                  className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-t-lg rounded-b-none border-b-2 data-[state=active]:border-amber-500 border-transparent px-4 py-2"
                >
                  <Image className="h-4 w-4 mr-1.5" />
                  Screenshots
                </TabsTrigger>
              )}
            </TabsList>
          </div>

          <ScrollArea className="flex-1 max-h-[50vh]">
            {/* Timeline Tab */}
            <TabsContent value="timeline" className="m-0 p-6">
              <div className="relative">
                {/* Vertical timeline line */}
                <div className="absolute left-[5px] top-3 bottom-3 w-px bg-slate-200" />
                <div className="space-y-1">
                  {run.logs.map((log, i) => (
                    <div key={i} className="relative flex items-start gap-3 pl-6 py-1.5 group">
                      {/* Dot on the timeline line */}
                      <div className="absolute left-0 top-2.5">
                        <StepStatusDot status={log.status} />
                      </div>
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-medium text-slate-500 whitespace-nowrap">
                            {formatShortTime(log.event_time)}
                          </span>
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-slate-200">
                            {log.action}
                          </Badge>
                          <span className={`text-[10px] font-medium px-1.5 py-0 rounded ${
                            ['success', 'complete', 'completed'].includes(log.status?.toLowerCase())
                              ? 'bg-emerald-50 text-emerald-700'
                              : ['failed', 'error'].includes(log.status?.toLowerCase())
                              ? 'bg-rose-50 text-rose-700'
                              : log.status?.toLowerCase() === 'warning'
                              ? 'bg-amber-50 text-amber-700'
                              : 'bg-slate-50 text-slate-600'
                          }`}>
                            {log.status}
                          </span>
                        </div>
                        <p className="text-sm text-slate-700 mt-0.5 break-words">{log.details}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>

            {/* Error Report Tab */}
            <TabsContent value="error-report" className="m-0 p-6">
              {loadingFiles ? (
                <div className="flex items-center justify-center py-12 text-slate-500">
                  <Loader2 className="h-5 w-5 animate-spin mr-2" />
                  Loading error reports...
                </div>
              ) : (
                <div className="space-y-4">
                  {txtFiles.map((file: ErrorFile) => (
                    <ErrorFileViewer key={file.filename} file={file} />
                  ))}
                  {jsonFiles.map((file: ErrorFile) => (
                    <ErrorFileViewer key={file.filename} file={file} />
                  ))}
                  {txtFiles.length === 0 && jsonFiles.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                      <FileText className="h-10 w-10 mb-3" />
                      <p>No error reports available</p>
                    </div>
                  )}
                </div>
              )}
            </TabsContent>

            {/* Screenshots Tab */}
            <TabsContent value="screenshots" className="m-0 p-6">
              {screenshotFiles.length > 0 ? (
                <div className="grid grid-cols-1 gap-4">
                  {screenshotFiles.map((file: ErrorFile) => (
                    <div key={file.filename} className="border border-slate-200 rounded-lg overflow-hidden">
                      <div className="bg-slate-50 px-3 py-2 border-b border-slate-200">
                        <p className="text-xs font-medium text-slate-600 truncate">{file.filename}</p>
                      </div>
                      <img
                        src={ENDPOINTS.ERROR_FILES.SCREENSHOT(file.filename)}
                        alt={file.filename}
                        className="w-full h-auto"
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                  <Image className="h-10 w-10 mb-3" />
                  <p>No screenshots available</p>
                </div>
              )}
            </TabsContent>
          </ScrollArea>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}

// ─── Error File Viewer ───────────────────────────────────────────

function ErrorFileViewer({ file }: { file: ErrorFile }) {
  const [expanded, setExpanded] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['errorFileContent', file.filename],
    queryFn: () => api.getErrorFileContent(file.filename),
    enabled: expanded,
  })

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          {file.type === 'report' ? (
            <FileText className="h-4 w-4 text-rose-500 shrink-0" />
          ) : (
            <FileText className="h-4 w-4 text-blue-500 shrink-0" />
          )}
          <span className="text-sm font-medium text-slate-700 truncate">{file.filename}</span>
          <span className="text-xs text-slate-400 shrink-0">
            ({(file.size / 1024).toFixed(1)} KB)
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-slate-400 shrink-0" />
        ) : (
          <ChevronDown className="h-4 w-4 text-slate-400 shrink-0" />
        )}
      </button>
      {expanded && (
        <div className="px-4 py-3 bg-white">
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm text-slate-500 py-4">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading file content...
            </div>
          ) : data?.type === 'text' ? (
            <pre className="text-xs text-slate-700 whitespace-pre-wrap font-mono bg-slate-50 rounded p-3 max-h-80 overflow-auto border border-slate-100">
              {data.content}
            </pre>
          ) : data?.type === 'json' ? (
            <div className="space-y-3">
              {/* Structured JSON display */}
              {data.content?.error_type && (
                <div className="bg-rose-50 border border-rose-100 rounded-lg p-3">
                  <p className="text-xs font-semibold text-rose-800 mb-1">Error Type</p>
                  <p className="text-sm text-rose-700">{data.content.error_type}: {data.content.error_message}</p>
                </div>
              )}
              {data.content?.automation_status && (
                <div className={`rounded-lg p-3 border ${
                  data.content.automation_status === 'FAILED' ? 'bg-rose-50 border-rose-100' :
                  data.content.automation_status === 'WARNING' ? 'bg-amber-50 border-amber-100' :
                  'bg-slate-50 border-slate-100'
                }`}>
                  <p className="text-xs font-semibold text-slate-800 mb-1">Status: {data.content.automation_status}</p>
                  <p className="text-sm text-slate-700">{data.content.error_summary}</p>
                </div>
              )}
              {data.content?.context && (
                <div className="bg-slate-50 border border-slate-100 rounded-lg p-3">
                  <p className="text-xs font-semibold text-slate-800 mb-1">Context</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(data.content.context).map(([k, v]) => (
                      <span key={k} className="text-xs bg-white border border-slate-200 rounded px-2 py-1">
                        <span className="text-slate-500">{k}:</span>{' '}
                        <span className="text-slate-800 font-medium">{String(v)}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {data.content?.formatted_traceback && (
                <div>
                  <p className="text-xs font-semibold text-slate-800 mb-1">Traceback</p>
                  <pre className="text-xs text-rose-700 bg-rose-50 rounded p-3 overflow-auto max-h-40 border border-rose-100 font-mono">
                    {data.content.formatted_traceback}
                  </pre>
                </div>
              )}
              {data.content?.suggested_actions && data.content.suggested_actions.length > 0 && (
                <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
                  <p className="text-xs font-semibold text-blue-800 mb-1">Suggested Actions</p>
                  <ul className="list-disc list-inside text-sm text-blue-700 space-y-0.5">
                    {data.content.suggested_actions.map((a: string, i: number) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
              {data.content?.failure_identification?.failure_point && (
                <div className="bg-rose-50 border border-rose-100 rounded-lg p-3">
                  <p className="text-xs font-semibold text-rose-800 mb-1">Failure Point</p>
                  <p className="text-sm text-rose-700">
                    {data.content.failure_identification.failure_point.action}: {data.content.failure_identification.failure_point.message}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-500">Unable to display file content</p>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Automation Run Card ─────────────────────────────────────────

function AutomationRunCard({
  run,
  onViewDetails,
}: {
  run: AutomationRun
  onViewDetails: () => void
}) {
  const statusBarColor: Record<string, string> = {
    completed: 'bg-emerald-500',
    failed: 'bg-rose-500',
    running: 'bg-blue-500',
    warning: 'bg-amber-500',
    unknown: 'bg-slate-300',
  }

  return (
    <div className="group relative bg-white rounded-xl border border-slate-200 hover:border-slate-300 hover:shadow-md transition-all duration-200 overflow-hidden">
      {/* Left status indicator bar */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${statusBarColor[run.overall_status]}`} />

      <div className="flex items-center gap-4 px-5 py-4 pl-6">
        {/* Status icon */}
        <div className="shrink-0">
          <StatusIcon status={run.overall_status} />
        </div>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold text-slate-800 truncate">
              {run.rfp_id}
            </h3>
            <StatusBadge status={run.overall_status} />
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap">
            <span className="flex items-center gap-1">
              <Activity className="h-3 w-3" />
              {run.action}
            </span>
            <span>|</span>
            <span>{formatShortTime(run.start_time)}</span>
            {run.start_time !== run.end_time && (
              <>
                <ArrowRight className="h-3 w-3" />
                <span>{formatShortTime(run.end_time)}</span>
              </>
            )}
          </div>
        </div>

        {/* Step progress summary */}
        <div className="hidden sm:flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-1.5 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-slate-600">{run.success_steps}</span>
          </div>
          {run.failed_steps > 0 && (
            <div className="flex items-center gap-1.5 text-xs">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              <span className="text-slate-600">{run.failed_steps}</span>
            </div>
          )}
          {run.warning_steps > 0 && (
            <div className="flex items-center gap-1.5 text-xs">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-slate-600">{run.warning_steps}</span>
            </div>
          )}
          <span className="text-xs text-slate-400">
            / {run.total_steps} steps
          </span>
        </div>

        {/* Eye view button */}
        <Button
          variant="outline"
          size="sm"
          onClick={onViewDetails}
          className="shrink-0 border-slate-200 hover:bg-indigo-50 hover:border-indigo-200 hover:text-indigo-700 transition-colors"
        >
          <Eye className="h-4 w-4 mr-1" />
          View
        </Button>
      </div>
    </div>
  )
}

// ─── Main Page ───────────────────────────────────────────────────

export default function LogsPage() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [selectedRun, setSelectedRun] = useState<AutomationRun | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['automationLogs', page, pageSize],
    queryFn: () => api.getAutomationLogs(page, pageSize),
  })

  const logs: LogEntry[] = data?.logs || []
  const totalRuns = data?.total_runs || 0
  const totalPages = Math.ceil(totalRuns / pageSize)

  // Group logs into automation runs
  const allRuns = useMemo(() => groupLogsByRunId(logs), [logs])

  // Filter runs
  const filteredRuns = useMemo(() => {
    let result = allRuns

    // Status filter
    if (statusFilter !== 'all') {
      result = result.filter((r) => r.overall_status === statusFilter)
    }

    // Search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase()
      result = result.filter((r) =>
        r.rfp_id.toLowerCase().includes(term) ||
        r.action.toLowerCase().includes(term) ||
        r.run_id.toLowerCase().includes(term) ||
        r.category.toLowerCase().includes(term) ||
        r.logs.some((l) => l.details?.toLowerCase().includes(term))
      )
    }

    return result
  }, [allRuns, statusFilter, searchTerm])

  // Stats
  const stats = useMemo(() => ({
    total: allRuns.length,
    completed: allRuns.filter((r) => r.overall_status === 'completed').length,
    failed: allRuns.filter((r) => r.overall_status === 'failed').length,
    running: allRuns.filter((r) => r.overall_status === 'running').length,
    warning: allRuns.filter((r) => r.overall_status === 'warning').length,
  }), [allRuns])

  const handleViewDetails = (run: AutomationRun) => {
    setSelectedRun(run)
    setModalOpen(true)
  }

  return (
    <PageWrapper
      title="Activity Logs"
      description="Monitor automation runs and track RFP processing history"
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
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <button
          onClick={() => setStatusFilter('all')}
          className={`rounded-xl p-4 text-left transition-all ${
            statusFilter === 'all' ? 'ring-2 ring-indigo-400 shadow-md' : ''
          } stat-card-blue`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">Total Runs</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{stats.total}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-white/60 flex items-center justify-center">
              <Activity className="h-5 w-5 text-indigo-600" />
            </div>
          </div>
        </button>

        <button
          onClick={() => setStatusFilter(statusFilter === 'completed' ? 'all' : 'completed')}
          className={`rounded-xl p-4 text-left transition-all ${
            statusFilter === 'completed' ? 'ring-2 ring-emerald-400 shadow-md' : ''
          } stat-card-emerald`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">Completed</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{stats.completed}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-white/60 flex items-center justify-center">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            </div>
          </div>
        </button>

        <button
          onClick={() => setStatusFilter(statusFilter === 'failed' ? 'all' : 'failed')}
          className={`rounded-xl p-4 text-left transition-all ${
            statusFilter === 'failed' ? 'ring-2 ring-rose-400 shadow-md' : ''
          } stat-card-rose`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">Failed</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{stats.failed}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-white/60 flex items-center justify-center">
              <XCircle className="h-5 w-5 text-rose-600" />
            </div>
          </div>
        </button>

        <button
          onClick={() => setStatusFilter(statusFilter === 'running' ? 'all' : 'running')}
          className={`rounded-xl p-4 text-left transition-all ${
            statusFilter === 'running' ? 'ring-2 ring-blue-400 shadow-md' : ''
          } stat-card-amber`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">Running</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{stats.running}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-white/60 flex items-center justify-center">
              <Loader2 className="h-5 w-5 text-blue-600" />
            </div>
          </div>
        </button>

        <button
          onClick={() => setStatusFilter(statusFilter === 'warning' ? 'all' : 'warning')}
          className={`rounded-xl p-4 text-left transition-all ${
            statusFilter === 'warning' ? 'ring-2 ring-amber-400 shadow-md' : ''
          } stat-card-amber`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">Warnings</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{stats.warning}</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-white/60 flex items-center justify-center">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            </div>
          </div>
        </button>
      </div>

      {/* Controls bar */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4 border-b border-slate-100 bg-slate-50/50">
          <CardTitle className="text-base font-semibold text-slate-800 flex items-center gap-2">
            <Activity className="h-5 w-5 text-indigo-600" />
            Automation Runs
            {statusFilter !== 'all' && (
              <Badge variant="secondary" className="ml-2 text-xs">
                <Filter className="h-3 w-3 mr-1" />
                {statusFilter}
              </Badge>
            )}
          </CardTitle>
          <div className="flex items-center gap-3">
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search by RFP ID, action..."
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
                <SelectItem value="50">50 rows</SelectItem>
                <SelectItem value="100">100 rows</SelectItem>
                <SelectItem value="200">200 rows</SelectItem>
                <SelectItem value="500">500 rows</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="flex items-center gap-4 p-4 rounded-xl border border-slate-100">
                  <Skeleton className="h-6 w-6 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-1/3" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                  <Skeleton className="h-8 w-16" />
                </div>
              ))}
            </div>
          ) : filteredRuns.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-500">
              <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                <Activity className="h-8 w-8 text-slate-400" />
              </div>
              <p className="text-lg font-medium text-slate-600 mb-2">No automation runs found</p>
              <p className="text-sm text-slate-400 mb-4">
                {searchTerm || statusFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : 'Automation runs will appear here'}
              </p>
              {(searchTerm || statusFilter !== 'all') && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setSearchTerm('')
                    setStatusFilter('all')
                  }}
                  className="border-slate-200"
                >
                  Clear Filters
                </Button>
              )}
            </div>
          ) : (
            <ScrollArea className="h-[520px]">
              <div className="p-4 space-y-2">
                {filteredRuns.map((run) => (
                  <AutomationRunCard
                    key={run.run_id}
                    run={run}
                    onViewDetails={() => handleViewDetails(run)}
                  />
                ))}
              </div>
            </ScrollArea>
          )}

          {/* Pagination */}
          {totalPages > 0 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50/50">
              <p className="text-sm text-slate-500">
                Showing <span className="font-semibold text-slate-700">{filteredRuns.length}</span> runs
                of <span className="font-semibold text-slate-700">{totalRuns}</span> total
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

      {/* Detail Modal */}
      <RunDetailModal
        run={selectedRun}
        open={modalOpen}
        onClose={() => {
          setModalOpen(false)
          setSelectedRun(null)
        }}
      />
    </PageWrapper>
  )
}
