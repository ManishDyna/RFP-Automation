import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Search,
  ArrowLeft,
  ExternalLink,
  FileSpreadsheet,
  RotateCcw,
  Filter,
  Calendar,
  Building2,
  ListFilter,
  TrendingUp,
  Clock,
  CheckCircle2,
  XCircle,
  Download,
} from 'lucide-react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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

const statusOptions = [
  { value: '', label: 'All Statuses' },
  { value: 'downloaded', label: 'Downloaded' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'declined', label: 'Declined' },
  { value: 'open', label: 'Open' },
]

function StatusBadge({ status }: { status: string }) {
  const statusMap: Record<string, { label: string; variant: 'warning' | 'success' | 'destructive' | 'secondary' | 'info'; icon: React.ElementType }> = {
    open: { label: 'Open', variant: 'warning', icon: Clock },
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

function StatCard({
  title,
  value,
  icon: Icon,
  trend,
  className
}: {
  title: string
  value: string | number
  icon: React.ElementType
  trend?: string
  className?: string
}) {
  return (
    <div className={`rounded-xl p-4 ${className}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-slate-600">{title}</p>
          <p className="text-2xl font-bold text-slate-800 mt-1">{value}</p>
          {trend && (
            <p className="text-xs text-emerald-600 font-medium mt-1 flex items-center gap-1">
              <TrendingUp className="h-3 w-3" />
              {trend}
            </p>
          )}
        </div>
        <div className="w-10 h-10 rounded-lg bg-white/60 flex items-center justify-center">
          <Icon className="h-5 w-5 text-slate-600" />
        </div>
      </div>
    </div>
  )
}

export default function RfpInsightsPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const [filters, setFilters] = useState({
    status: searchParams.get('status') || '',
    company: searchParams.get('company') || '',
    start_date: searchParams.get('start_date') || '',
    end_date: searchParams.get('end_date') || '',
    search: searchParams.get('search') || '',
  })

  const { data, isLoading } = useQuery({
    queryKey: ['rfpDetails', filters],
    queryFn: () => api.getRfpDetails(filters),
  })

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const handleApplyFilters = () => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      // Skip 'all' values as they mean no filter
      if (value && value !== 'all') params.set(key, value)
    })
    setSearchParams(params)
  }

  const handleReset = () => {
    setFilters({
      status: '',
      company: '',
      start_date: '',
      end_date: '',
      search: '',
    })
    setSearchParams({})
  }

  const [downloadingRfpId, setDownloadingRfpId] = useState<string | null>(null)

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

  const rfps = data?.rfps || []
  const uniqueCompanies = data?.unique_companies || []
  const totalRows = data?.total_rows || 0
  const shownRows = data?.shown_rows || rfps.length

  // Calculate stats
  const submittedCount = rfps.filter((r: any) => r.status?.toLowerCase() === 'submitted').length
  const openCount = rfps.filter((r: any) => r.status?.toLowerCase() === 'open').length
  const downloadedCount = rfps.filter((r: any) => r.status?.toLowerCase() === 'downloaded').length

  return (
    <PageWrapper
      title="RFP Insights"
      description="Analyze and manage all your RFP data with powerful filters and quick actions."
      actions={
        <Button variant="outline" asChild className="border-slate-200 hover:bg-slate-50">
          <Link to="/dashboard">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Dashboard
          </Link>
        </Button>
      }
    >
      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard
          title="Total RFPs"
          value={totalRows}
          icon={FileSpreadsheet}
          className="stat-card-blue"
        />
        <StatCard
          title="Submitted"
          value={submittedCount}
          icon={CheckCircle2}
          className="stat-card-emerald"
        />
        <StatCard
          title="Open"
          value={openCount}
          icon={Clock}
          className="stat-card-amber"
        />
        <StatCard
          title="Downloaded"
          value={downloadedCount}
          icon={Download}
          className="stat-card-rose"
        />
      </div>

      {/* Filters Card */}
      <Card className="mb-6 border-slate-200 shadow-sm">
        <CardHeader className="pb-4">
          <CardTitle className="text-base font-semibold text-slate-700 flex items-center gap-2">
            <Filter className="h-4 w-4 text-indigo-500" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6">
            <div className="space-y-2">
              <Label htmlFor="status" className="text-slate-600 text-sm flex items-center gap-1.5">
                <ListFilter className="h-3.5 w-3.5" />
                Status
              </Label>
              <Select
                value={filters.status || 'all'}
                onValueChange={(value) => handleFilterChange('status', value === 'all' ? '' : value)}
              >
                <SelectTrigger id="status" className="bg-slate-50 border-slate-200 focus:bg-white">
                  <SelectValue placeholder="All Statuses" />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((option) => (
                    <SelectItem key={option.value || 'all'} value={option.value || 'all'}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="company" className="text-slate-600 text-sm flex items-center gap-1.5">
                <Building2 className="h-3.5 w-3.5" />
                Company
              </Label>
              <Select
                value={filters.company || 'all'}
                onValueChange={(value) => handleFilterChange('company', value === 'all' ? '' : value)}
              >
                <SelectTrigger id="company" className="bg-slate-50 border-slate-200 focus:bg-white">
                  <SelectValue placeholder="All Companies" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Companies</SelectItem>
                  {uniqueCompanies.map((company: string) => (
                    <SelectItem key={company} value={company}>
                      {company}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="start_date" className="text-slate-600 text-sm flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5" />
                Start Date
              </Label>
              <Input
                id="start_date"
                type="date"
                value={filters.start_date}
                onChange={(e) => handleFilterChange('start_date', e.target.value)}
                className="bg-slate-50 border-slate-200 focus:bg-white"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="end_date" className="text-slate-600 text-sm flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5" />
                End Date
              </Label>
              <Input
                id="end_date"
                type="date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                className="bg-slate-50 border-slate-200 focus:bg-white"
              />
            </div>

            <div className="space-y-2 lg:col-span-2">
              <Label htmlFor="search" className="text-slate-600 text-sm flex items-center gap-1.5">
                <Search className="h-3.5 w-3.5" />
                Search
              </Label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <Input
                    id="search"
                    placeholder="Search RFP ID, company, owner..."
                    value={filters.search}
                    onChange={(e) => handleFilterChange('search', e.target.value)}
                    className="pl-10 bg-slate-50 border-slate-200 focus:bg-white"
                    onKeyDown={(e) => e.key === 'Enter' && handleApplyFilters()}
                  />
                </div>
                <Button
                  onClick={handleApplyFilters}
                  className="bg-indigo-600 hover:bg-indigo-700 shadow-sm"
                >
                  <Filter className="h-4 w-4 mr-2" />
                  Apply
                </Button>
                <Button
                  variant="outline"
                  onClick={handleReset}
                  className="border-slate-200 hover:bg-slate-50"
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Reset
                </Button>
              </div>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-slate-500">
              Showing <span className="font-semibold text-slate-700">{shownRows}</span> of{' '}
              <span className="font-semibold text-slate-700">{totalRows}</span> RFPs
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Results Table */}
      <Card className="border-slate-200 shadow-sm overflow-hidden">
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex items-center gap-4">
                  <Skeleton className="h-10 w-24" />
                  <Skeleton className="h-10 flex-1" />
                  <Skeleton className="h-10 w-32" />
                  <Skeleton className="h-10 w-24" />
                </div>
              ))}
            </div>
          ) : rfps.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-500">
              <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                <Search className="h-8 w-8 text-slate-400" />
              </div>
              <p className="text-lg font-medium text-slate-600 mb-2">No RFPs found</p>
              <p className="text-sm text-slate-400 mb-4">Try adjusting your filters to find what you're looking for</p>
              <Button variant="outline" onClick={handleReset} className="border-slate-200">
                <RotateCcw className="h-4 w-4 mr-2" />
                Clear All Filters
              </Button>
            </div>
          ) : (
            <ScrollArea className="h-[520px]">
              <Table>
                <TableHeader className="sticky top-0 bg-slate-50/95 backdrop-blur-sm z-10">
                  <TableRow className="border-slate-200 hover:bg-slate-50/95">
                    <TableHead className="text-slate-600 font-semibold">RFP ID</TableHead>
                    <TableHead className="text-slate-600 font-semibold">Company</TableHead>
                    <TableHead className="text-slate-600 font-semibold">Owner</TableHead>
                    <TableHead className="text-slate-600 font-semibold">Published</TableHead>
                    <TableHead className="text-slate-600 font-semibold">Deadline</TableHead>
                    <TableHead className="text-slate-600 font-semibold">Status</TableHead>
                    <TableHead className="text-slate-600 font-semibold text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rfps.map((rfp: any, index: number) => (
                    <TableRow
                      key={rfp.RFP_ID || index}
                      className="border-slate-100 hover:bg-slate-50/50 transition-colors"
                    >
                      <TableCell className="font-medium">
                        {rfp.Link ? (
                          <a
                            href={rfp.Link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-indigo-600 hover:text-indigo-700 hover:underline inline-flex items-center gap-1.5 font-semibold"
                          >
                            {rfp.RFP_ID}
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        ) : (
                          <span className="text-slate-700">{rfp.RFP_ID}</span>
                        )}
                      </TableCell>
                      <TableCell className="text-slate-600">
                        {rfp.Company_Name || 'Saudi Electricity Company'}
                      </TableCell>
                      <TableCell className="text-slate-600">{rfp.Owner_Name || '-'}</TableCell>
                      <TableCell className="text-slate-500 text-sm">{rfp.Publish_Time || '-'}</TableCell>
                      <TableCell className="text-slate-500 text-sm">{rfp.RFP_End_Date || '-'}</TableCell>
                      <TableCell>
                        <StatusBadge status={rfp.status_label || rfp.status || 'downloaded'} />
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {rfp.Link && (
                            <Button
                              size="sm"
                              variant="outline"
                              asChild
                              className="h-8 border-slate-200 hover:bg-slate-50 hover:border-indigo-200 hover:text-indigo-600"
                            >
                              <a href={rfp.Link} target="_blank" rel="noopener noreferrer">
                                <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                                Portal
                              </a>
                            </Button>
                          )}
                          <Button
                            size="sm"
                            className="h-8 bg-emerald-600 hover:bg-emerald-700 shadow-sm"
                            disabled={downloadingRfpId === rfp.RFP_ID}
                            onClick={() => handleDownloadExcel(rfp.RFP_ID, rfp.Company_Name)}
                          >
                            <FileSpreadsheet className={`h-3.5 w-3.5 mr-1.5 ${downloadingRfpId === rfp.RFP_ID ? 'animate-spin' : ''}`} />
                            {downloadingRfpId === rfp.RFP_ID ? 'Downloading...' : 'Excel'}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </PageWrapper>
  )
}
