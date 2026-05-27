import { useState, useCallback, useRef, useEffect } from 'react'
import { useHasPermission } from '@/hooks/use-auth'
import { formatDateMDY } from '@/lib/utils'
import { useInfiniteQuery } from '@tanstack/react-query'
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
  Clock,
  CheckCircle2,
  XCircle,
  Download,
  Columns3,
} from 'lucide-react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { StatCard } from '@/components/shared/stat-card'
import { StatusBadge } from '@/components/shared/status-badge'
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
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { api } from '@/lib/api'
import { SharePointButton } from '@/components/shared/sharepoint-button'

const statusOptions = [
  { value: '', label: 'All Statuses' },
  { value: 'open', label: 'Open' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'declined', label: 'Declined' },
  { value: 'not_participant', label: 'Not Participant' },
]

const materialMatchOptions = [
  { value: '', label: 'All' },
  { value: 'matched', label: 'Matched' },
  { value: 'not_matched', label: 'Not Matched' },
]

const keywordMatchOptions = [
  { value: '', label: 'All' },
  { value: 'matched', label: 'Matched' },
  { value: 'not_matched', label: 'Not Matched' },
]

const participationOptions = [
  { value: '', label: 'All' },
  { value: 'participated', label: 'Participated' },
  { value: 'not_participated', label: 'Not Participated' },
  { value: 'declined', label: 'Declined' },
]

// Define available columns
const AVAILABLE_COLUMNS = {
  company: { label: 'Company', default: true },
  owner: { label: 'Owner', default: true },
  published: { label: 'Published', default: true },
  deadline: { label: 'Deadline', default: true },
  status: { label: 'Status', default: true },
  participation: { label: 'Participation', default: true },
  materialMatch: { label: 'Material Code Match', default: false },
  keywordMatch: { label: 'Keyword Match', default: false },
} as const

export default function RfpInsightsPage() {
  const canDownloadRfp = useHasPermission('rfp.download')
  const canSharePointRfp = useHasPermission('rfp.sharepoint.view')
  const [searchParams, setSearchParams] = useSearchParams()
  const [filters, setFilters] = useState({
    status: searchParams.get('status') || '',
    company: searchParams.get('company') || '',
    start_date: searchParams.get('start_date') || '',
    end_date: searchParams.get('end_date') || '',
    search: searchParams.get('search') || '',
    material_match: searchParams.get('material_match') || '',
    keyword_match: searchParams.get('keyword_match') || '',
    participation: searchParams.get('participation') || '',
  })

  // Column visibility state with localStorage persistence
  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(() => {
    const stored = localStorage.getItem('rfp-insights-columns')
    if (stored) {
      try {
        return JSON.parse(stored)
      } catch {
        // If parsing fails, use defaults
      }
    }
    // Default: all columns visible
    return Object.keys(AVAILABLE_COLUMNS).reduce((acc, key) => {
      acc[key] = AVAILABLE_COLUMNS[key as keyof typeof AVAILABLE_COLUMNS].default
      return acc
    }, {} as Record<string, boolean>)
  })

  // Save column visibility to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('rfp-insights-columns', JSON.stringify(visibleColumns))
  }, [visibleColumns])

  const toggleColumn = (columnKey: string) => {
    setVisibleColumns(prev => ({ ...prev, [columnKey]: !prev[columnKey] }))
  }

  const scrollRef = useRef<HTMLDivElement>(null)

  const ITEMS_PER_PAGE = 50

  const {
    data,
    isLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['rfpDetails', filters],
    queryFn: ({ pageParam = 0 }) =>
      api.getRfpDetails({ ...filters, limit: ITEMS_PER_PAGE, offset: pageParam }),
    getNextPageParam: (lastPage) => {
      if (lastPage.has_more) {
        return lastPage.offset + lastPage.limit
      }
      return undefined
    },
    initialPageParam: 0,
  })

  // Flatten all pages of data
  const rawRfps = data?.pages.flatMap(page => page.rfps) || []
  const uniqueCompanies = data?.pages[0]?.unique_companies || []
  const totalRows = data?.pages[0]?.total_rows || 0
  const totalFiltered = data?.pages[0]?.total_filtered || 0
  const statusCounts = data?.pages[0]?.status_counts || {}
  const totalStatusCounts = data?.pages[0]?.total_status_counts || {}

  const allRfps = rawRfps

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

  // Scroll detection for lazy loading
  useEffect(() => {
    const scrollArea = scrollRef.current
    if (!scrollArea) return

    // Get the viewport element from Radix UI ScrollArea
    const viewport = scrollArea.querySelector('[data-radix-scroll-area-viewport]')
    if (!viewport) return

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = viewport
      // Load more when user scrolls to within 200px of the bottom
      if (scrollHeight - scrollTop - clientHeight < 200 && hasNextPage && !isFetchingNextPage) {
        fetchNextPage()
      }
    }

    viewport.addEventListener('scroll', handleScroll)
    return () => viewport.removeEventListener('scroll', handleScroll)
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const handleReset = () => {
    setFilters({
      status: '',
      company: '',
      start_date: '',
      end_date: '',
      search: '',
      material_match: '',
      keyword_match: '',
      participation: '',
    })
    setSearchParams({})
  }

  const [downloadingRfpId, setDownloadingRfpId] = useState<string | null>(null)
  const [exportingFormat, setExportingFormat] = useState<string | null>(null)

  const handleExport = useCallback(async (format: 'csv' | 'excel') => {
    setExportingFormat(format)
    try {
      await api.exportRfpData(filters, format)
      toast.success(`RFP data exported as ${format === 'excel' ? 'Excel' : 'CSV'} successfully`)
    } catch (error: any) {
      toast.error(error.message || `Failed to export ${format === 'excel' ? 'Excel' : 'CSV'}`)
    } finally {
      setExportingFormat(null)
    }
  }, [filters])

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

  // Check if any filters are active
  const hasActiveFilters = !!(
    filters.status ||
    filters.company ||
    filters.start_date ||
    filters.end_date ||
    filters.search ||
    filters.material_match ||
    filters.keyword_match ||
    filters.participation
  )

  // Use filtered counts when filters are active, otherwise use total counts
  const countsToUse = hasActiveFilters ? statusCounts : totalStatusCounts

  // Calculate stats from API response (based on filtered or total data)
  const totalRfpsCount = hasActiveFilters ? totalFiltered : totalRows
  const submittedCount = countsToUse.submitted || 0
  const notParticipantCount = countsToUse.not_participant || 0
  const declinedCount = countsToUse.declined || 0
  const openCount = countsToUse.open || 0

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
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <StatCard
          title="Total RFPs"
          value={totalRfpsCount}
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
          title="Declined"
          value={declinedCount}
          icon={XCircle}
          className="stat-card-rose"
        />
        <StatCard
          title="Not Participant"
          value={notParticipantCount}
          icon={XCircle}
          className="stat-card-amber"
        />
        <StatCard
          title="Open"
          value={openCount}
          icon={Clock}
          className="stat-card-violet"
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
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
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

            <div className="space-y-2">
              <Label htmlFor="material_match" className="text-slate-600 text-sm flex items-center gap-1.5">
                <ListFilter className="h-3.5 w-3.5" />
                Material Code Match
              </Label>
              <Select
                value={filters.material_match || 'all'}
                onValueChange={(value) => handleFilterChange('material_match', value === 'all' ? '' : value)}
              >
                <SelectTrigger id="material_match" className="bg-slate-50 border-slate-200 focus:bg-white">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  {materialMatchOptions.map((option) => (
                    <SelectItem key={option.value || 'all'} value={option.value || 'all'}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="keyword_match" className="text-slate-600 text-sm flex items-center gap-1.5">
                <ListFilter className="h-3.5 w-3.5" />
                Keyword Match
              </Label>
              <Select
                value={filters.keyword_match || 'all'}
                onValueChange={(value) => handleFilterChange('keyword_match', value === 'all' ? '' : value)}
              >
                <SelectTrigger id="keyword_match" className="bg-slate-50 border-slate-200 focus:bg-white">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  {keywordMatchOptions.map((option) => (
                    <SelectItem key={option.value || 'all'} value={option.value || 'all'}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="participation" className="text-slate-600 text-sm flex items-center gap-1.5">
                <ListFilter className="h-3.5 w-3.5" />
                Participation
              </Label>
              <Select
                value={filters.participation || 'all'}
                onValueChange={(value) => handleFilterChange('participation', value === 'all' ? '' : value)}
              >
                <SelectTrigger id="participation" className="bg-slate-50 border-slate-200 focus:bg-white">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  {participationOptions.map((option) => (
                    <SelectItem key={option.value || 'all'} value={option.value || 'all'}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2 xl:col-span-3">
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
              Showing <span className="font-semibold text-slate-700">{allRfps.length}</span> of{' '}
              <span className="font-semibold text-slate-700">{hasActiveFilters ? totalFiltered : totalRows}</span> RFPs
              {hasActiveFilters && totalFiltered !== totalRows && (
                <span className="text-slate-400"> ({totalRows} total)</span>
              )}
            </p>
            <div className="flex items-center gap-3">
              {/* Export Buttons */}
              <Button
                variant="outline"
                size="sm"
                className="border-slate-200 hover:bg-slate-50"
                disabled={exportingFormat === 'csv'}
                onClick={() => handleExport('csv')}
              >
                <Download className={`h-4 w-4 mr-2 ${exportingFormat === 'csv' ? 'animate-spin' : ''}`} />
                {exportingFormat === 'csv' ? 'Exporting...' : 'Export CSV'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                disabled={exportingFormat === 'excel'}
                onClick={() => handleExport('excel')}
              >
                <FileSpreadsheet className={`h-4 w-4 mr-2 ${exportingFormat === 'excel' ? 'animate-spin' : ''}`} />
                {exportingFormat === 'excel' ? 'Exporting...' : 'Export Excel'}
              </Button>
              {/* Column Visibility Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-slate-200 hover:bg-slate-50"
                  >
                    <Columns3 className="h-4 w-4 mr-2" />
                    Columns
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuLabel>Toggle Columns</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {Object.entries(AVAILABLE_COLUMNS).map(([key, config]) => (
                    <DropdownMenuCheckboxItem
                      key={key}
                      checked={visibleColumns[key]}
                      onCheckedChange={() => toggleColumn(key)}
                    >
                      {config.label}
                    </DropdownMenuCheckboxItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              {hasNextPage && (
                <p className="text-sm text-indigo-600 font-medium">
                  Scroll down to load more...
                </p>
              )}
            </div>
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
          ) : allRfps.length === 0 && !isLoading ? (
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
            <ScrollArea className="h-[520px]" ref={scrollRef}>
              <Table>
                <TableHeader className="sticky top-0 bg-slate-50/95 backdrop-blur-sm z-10">
                  <TableRow className="border-slate-200 hover:bg-slate-50/95">
                    <TableHead className="text-slate-600 font-semibold">RFP ID</TableHead>
                    {visibleColumns.company && (
                      <TableHead className="text-slate-600 font-semibold">Company</TableHead>
                    )}
                    {visibleColumns.owner && (
                      <TableHead className="text-slate-600 font-semibold">Owner</TableHead>
                    )}
                    {visibleColumns.published && (
                      <TableHead className="text-slate-600 font-semibold">Published</TableHead>
                    )}
                    {visibleColumns.deadline && (
                      <TableHead className="text-slate-600 font-semibold">Deadline</TableHead>
                    )}
                    {visibleColumns.materialMatch && (
                      <TableHead className="text-slate-600 font-semibold">Material Code Match</TableHead>
                    )}
                    {visibleColumns.keywordMatch && (
                      <TableHead className="text-slate-600 font-semibold">Keyword Match</TableHead>
                    )}
                    {visibleColumns.status && (
                      <TableHead className="text-slate-600 font-semibold">Status</TableHead>
                    )}
                    {visibleColumns.participation && (
                      <TableHead className="text-slate-600 font-semibold">Participation</TableHead>
                    )}
                    <TableHead className="text-slate-600 font-semibold text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allRfps.map((rfp: any, index: number) => (
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
                      {visibleColumns.company && (
                        <TableCell className="text-slate-600">
                          {rfp.Company_Name || 'Saudi Energy'}
                        </TableCell>
                      )}
                      {visibleColumns.owner && (
                        <TableCell className="text-slate-600">{rfp.Owner_Name || '-'}</TableCell>
                      )}
                      {visibleColumns.published && (
                        <TableCell className="text-slate-500 text-sm">{formatDateMDY(rfp.Publish_Time)}</TableCell>
                      )}
                      {visibleColumns.deadline && (
                        <TableCell className="text-slate-500 text-sm">{formatDateMDY(rfp.RFP_End_Date)}</TableCell>
                      )}
                      {visibleColumns.materialMatch && (
                        <TableCell>
                          {(rfp.Material_Matched || '').toLowerCase() === 'yes' ? (
                            <Badge variant="success" className="gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              Matched
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="gap-1">
                              <XCircle className="h-3 w-3" />
                              Not Matched
                            </Badge>
                          )}
                        </TableCell>
                      )}
                      {visibleColumns.keywordMatch && (
                        <TableCell>
                          {(rfp.Keyword_Matched || '').toLowerCase() === 'yes' ? (
                            <Badge variant="success" className="gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              Matched
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="gap-1">
                              <XCircle className="h-3 w-3" />
                              Not Matched
                            </Badge>
                          )}
                        </TableCell>
                      )}
                      {visibleColumns.status && (
                        <TableCell>
                          <StatusBadge status={rfp.status_label || rfp.status || 'downloaded'} />
                        </TableCell>
                      )}
                      {visibleColumns.participation && (
                        <TableCell>
                          {rfp.status_key === 'submitted' ? (
                            <Badge variant="success" className="gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              Participated
                            </Badge>
                          ) : rfp.status_key === 'declined' ? (
                            <Badge variant="destructive" className="gap-1">
                              <XCircle className="h-3 w-3" />
                              Declined
                            </Badge>
                          ) : rfp.status_key === 'not_participant' ? (
                            <Badge variant="destructive" className="gap-1">
                              <XCircle className="h-3 w-3" />
                              Not Participant
                            </Badge>
                          ) : (
                            <Badge variant="warning" className="gap-1">
                              <Clock className="h-3 w-3" />
                              Open
                            </Badge>
                          )}
                        </TableCell>
                      )}
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
                          {canSharePointRfp && (
                            <SharePointButton
                              rfpId={rfp.RFP_ID}
                              company={rfp.Company_Name}
                              variant="labeled"
                            />
                          )}
                          {canDownloadRfp && (
                            <Button
                              size="sm"
                              className="h-8 bg-emerald-600 hover:bg-emerald-700 shadow-sm"
                              disabled={downloadingRfpId === rfp.RFP_ID}
                              onClick={() => handleDownloadExcel(rfp.RFP_ID, rfp.Company_Name)}
                            >
                              <FileSpreadsheet className={`h-3.5 w-3.5 mr-1.5 ${downloadingRfpId === rfp.RFP_ID ? 'animate-spin' : ''}`} />
                              {downloadingRfpId === rfp.RFP_ID ? 'Downloading...' : 'Excel'}
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {isFetchingNextPage && (
                    <TableRow>
                      <TableCell colSpan={Object.values(visibleColumns).filter(Boolean).length + 2} className="text-center py-8">
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-5 h-5 border-3 border-slate-200 border-t-indigo-600 rounded-full animate-spin" />
                          <span className="text-sm text-slate-500">Loading more RFPs...</span>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

    </PageWrapper>
  )
}
