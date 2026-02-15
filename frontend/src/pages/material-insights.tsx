import { useState, useRef, useEffect, useMemo } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Search,
  ArrowLeft,
  Filter,
  Building2,
  ListFilter,
  TrendingUp,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Columns3,
  Package,
  Tag,
  Layers,
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
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { api } from '@/lib/api'

function StatCard({
  title,
  value,
  icon: Icon,
  trend,
  className,
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

const AVAILABLE_COLUMNS = {
  rfpId: { label: 'RFP ID', default: true },
  company: { label: 'Company', default: true },
  materialMatched: { label: 'Material Matched', default: true },
  keywordMatched: { label: 'Keyword Matched', default: true },
} as const

export default function MaterialInsightsPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const [filters, setFilters] = useState({
    company: searchParams.get('company') || '',
    rfp_id: searchParams.get('rfp_id') || '',
    material_match: searchParams.get('material_match') || '',
    keyword_match: searchParams.get('keyword_match') || '',
    search: searchParams.get('search') || '',
  })

  const [visibleColumns, setVisibleColumns] = useState<Record<string, boolean>>(() => {
    const stored = localStorage.getItem('material-insights-columns')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        // Only use stored value if it has valid keys matching current columns
        if ('rfpId' in parsed && !('materialCode' in parsed)) {
          return parsed
        }
      } catch {
        // fallback
      }
    }
    return Object.keys(AVAILABLE_COLUMNS).reduce((acc, key) => {
      acc[key] = AVAILABLE_COLUMNS[key as keyof typeof AVAILABLE_COLUMNS].default
      return acc
    }, {} as Record<string, boolean>)
  })

  useEffect(() => {
    localStorage.setItem('material-insights-columns', JSON.stringify(visibleColumns))
  }, [visibleColumns])

  const toggleColumn = (columnKey: string) => {
    setVisibleColumns((prev) => ({ ...prev, [columnKey]: !prev[columnKey] }))
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
    queryKey: ['materialInsights', filters],
    queryFn: ({ pageParam = 0 }) =>
      api.getMaterialInsights({ ...filters, limit: ITEMS_PER_PAGE, offset: pageParam }),
    getNextPageParam: (lastPage) => {
      if (lastPage.has_more) {
        return lastPage.offset + lastPage.limit
      }
      return undefined
    },
    initialPageParam: 0,
  })

  const allMaterials = data?.pages.flatMap((page) => page.materials) || []
  const stats = data?.pages[0]?.stats || {}
  const uniqueRfps: Record<string, string[]> = data?.pages[0]?.unique_rfps || {}
  const totalFiltered = data?.pages[0]?.total_filtered || 0
  const totalAll = data?.pages[0]?.total || 0

  // Build company list and RFP list for filters
  const uniqueCompanies = useMemo(() => Object.keys(uniqueRfps).sort(), [uniqueRfps])
  const rfpOptions = useMemo(() => {
    if (filters.company && uniqueRfps[filters.company]) {
      return uniqueRfps[filters.company]
    }
    const all: string[] = []
    Object.values(uniqueRfps).forEach((ids) => all.push(...ids))
    return [...new Set(all)].sort()
  }, [uniqueRfps, filters.company])

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => {
      const next = { ...prev, [key]: value }
      if (key === 'company') {
        next.rfp_id = ''
      }
      return next
    })
  }

  const handleApplyFilters = () => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value && value !== 'all') params.set(key, value)
    })
    setSearchParams(params)
  }

  // Scroll detection for lazy loading
  useEffect(() => {
    const scrollArea = scrollRef.current
    if (!scrollArea) return

    const viewport = scrollArea.querySelector('[data-radix-scroll-area-viewport]')
    if (!viewport) return

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = viewport
      if (scrollHeight - scrollTop - clientHeight < 200 && hasNextPage && !isFetchingNextPage) {
        fetchNextPage()
      }
    }

    viewport.addEventListener('scroll', handleScroll)
    return () => viewport.removeEventListener('scroll', handleScroll)
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const handleReset = () => {
    setFilters({
      company: '',
      rfp_id: '',
      material_match: '',
      keyword_match: '',
      search: '',
    })
    setSearchParams({})
  }

  const hasActiveFilters = !!(filters.company || filters.rfp_id || filters.material_match || filters.keyword_match || filters.search)

  return (
    <PageWrapper
      title="Material Insights"
      description="Analyze material and keyword matching data across all RFPs."
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
          value={hasActiveFilters ? totalFiltered : stats.total_rfps || 0}
          icon={Layers}
          className="stat-card-blue"
        />
        <StatCard
          title="Material Matched"
          value={stats.material_matched_count || 0}
          icon={Package}
          className="stat-card-emerald"
        />
        <StatCard
          title="Keyword Matched"
          value={stats.keyword_matched_count || 0}
          icon={Tag}
          className="stat-card-amber"
        />
        <StatCard
          title="Not Matched"
          value={stats.not_matched_count || 0}
          icon={XCircle}
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
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
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
                  {uniqueCompanies.map((company) => (
                    <SelectItem key={company} value={company}>
                      {company}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="rfp_id" className="text-slate-600 text-sm flex items-center gap-1.5">
                <ListFilter className="h-3.5 w-3.5" />
                RFP
              </Label>
              <Select
                value={filters.rfp_id || 'all'}
                onValueChange={(value) => handleFilterChange('rfp_id', value === 'all' ? '' : value)}
              >
                <SelectTrigger id="rfp_id" className="bg-slate-50 border-slate-200 focus:bg-white">
                  <SelectValue placeholder="All RFPs" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All RFPs</SelectItem>
                  {rfpOptions.map((rfp) => (
                    <SelectItem key={rfp} value={rfp}>
                      {rfp}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="material_match" className="text-slate-600 text-sm flex items-center gap-1.5">
                <Package className="h-3.5 w-3.5" />
                Material Matched
              </Label>
              <Select
                value={filters.material_match || 'all'}
                onValueChange={(value) => handleFilterChange('material_match', value === 'all' ? '' : value)}
              >
                <SelectTrigger id="material_match" className="bg-slate-50 border-slate-200 focus:bg-white">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="yes">Yes</SelectItem>
                  <SelectItem value="no">No</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="keyword_match" className="text-slate-600 text-sm flex items-center gap-1.5">
                <Tag className="h-3.5 w-3.5" />
                Keyword Matched
              </Label>
              <Select
                value={filters.keyword_match || 'all'}
                onValueChange={(value) => handleFilterChange('keyword_match', value === 'all' ? '' : value)}
              >
                <SelectTrigger id="keyword_match" className="bg-slate-50 border-slate-200 focus:bg-white">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="yes">Yes</SelectItem>
                  <SelectItem value="no">No</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="search" className="text-slate-600 text-sm flex items-center gap-1.5">
                <Search className="h-3.5 w-3.5" />
                Search
              </Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  id="search"
                  placeholder="Search RFP ID, company..."
                  value={filters.search}
                  onChange={(e) => handleFilterChange('search', e.target.value)}
                  className="pl-10 bg-slate-50 border-slate-200 focus:bg-white"
                  onKeyDown={(e) => e.key === 'Enter' && handleApplyFilters()}
                />
              </div>
            </div>
          </div>

          <div className="mt-4 flex gap-2">
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

          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-slate-500">
              Showing <span className="font-semibold text-slate-700">{allMaterials.length}</span> of{' '}
              <span className="font-semibold text-slate-700">{totalFiltered}</span> RFPs
              {totalFiltered !== totalAll && (
                <span className="text-slate-400"> ({totalAll} total)</span>
              )}
            </p>
            <div className="flex items-center gap-3">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="border-slate-200 hover:bg-slate-50">
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
                <p className="text-sm text-indigo-600 font-medium">Scroll down to load more...</p>
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
          ) : allMaterials.length === 0 && !isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-500">
              <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                <Search className="h-8 w-8 text-slate-400" />
              </div>
              <p className="text-lg font-medium text-slate-600 mb-2">No RFPs found</p>
              <p className="text-sm text-slate-400 mb-4">
                Try adjusting your filters to find what you're looking for
              </p>
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
                    {visibleColumns.rfpId && (
                      <TableHead className="text-slate-600 font-semibold">RFP ID</TableHead>
                    )}
                    {visibleColumns.company && (
                      <TableHead className="text-slate-600 font-semibold">Company</TableHead>
                    )}
                    {visibleColumns.materialMatched && (
                      <TableHead className="text-slate-600 font-semibold">Material Matched</TableHead>
                    )}
                    {visibleColumns.keywordMatched && (
                      <TableHead className="text-slate-600 font-semibold">Keyword Matched</TableHead>
                    )}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allMaterials.map((mat: any, index: number) => (
                    <TableRow
                      key={`${mat.rfp_id}-${index}`}
                      className="border-slate-100 hover:bg-slate-50/50 transition-colors"
                    >
                      {visibleColumns.rfpId && (
                        <TableCell className="font-medium text-indigo-600">{mat.rfp_id}</TableCell>
                      )}
                      {visibleColumns.company && (
                        <TableCell className="text-slate-600">{mat.company}</TableCell>
                      )}
                      {visibleColumns.materialMatched && (
                        <TableCell>
                          {mat.material_matched === 'Yes' ? (
                            <Badge variant="success" className="gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              Yes
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="gap-1">
                              <XCircle className="h-3 w-3" />
                              No
                            </Badge>
                          )}
                        </TableCell>
                      )}
                      {visibleColumns.keywordMatched && (
                        <TableCell>
                          {mat.keyword_matched === 'Yes' ? (
                            <Badge variant="success" className="gap-1">
                              <CheckCircle2 className="h-3 w-3" />
                              Yes
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="gap-1">
                              <XCircle className="h-3 w-3" />
                              No
                            </Badge>
                          )}
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                  {isFetchingNextPage && (
                    <TableRow>
                      <TableCell
                        colSpan={Object.values(visibleColumns).filter(Boolean).length}
                        className="text-center py-8"
                      >
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-5 h-5 border-3 border-slate-200 border-t-indigo-600 rounded-full animate-spin" />
                          <span className="text-sm text-slate-500">Loading more...</span>
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
