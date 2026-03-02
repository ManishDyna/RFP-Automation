import { useState, useRef, useEffect, useMemo, Fragment } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Search,
  ArrowLeft,
  Filter,
  Building2,
  TrendingUp,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Package,
  Tag,
  Layers,
  BarChart3,
  Send,
  ChevronDown,
  ChevronRight,
  Hash,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts'

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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
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

export default function MaterialInsightsPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const [activeTab, setActiveTab] = useState<string>(searchParams.get('tab') || 'materials')
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  const initialFilters = {
    company: searchParams.get('company') || '',
    participated: searchParams.get('participated') || '',
    search: searchParams.get('search') || '',
  }

  const [filters, setFilters] = useState(initialFilters)
  const [appliedFilters, setAppliedFilters] = useState(initialFilters)

  const scrollRef = useRef<HTMLDivElement>(null)
  const ITEMS_PER_PAGE = 50

  const {
    data,
    isLoading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['materialInsightsGrouped', activeTab, appliedFilters],
    queryFn: ({ pageParam = 0 }) =>
      api.getMaterialInsightsGrouped({
        tab: activeTab,
        ...appliedFilters,
        limit: ITEMS_PER_PAGE,
        offset: pageParam,
      }),
    getNextPageParam: (lastPage) => {
      if (lastPage.has_more) {
        return lastPage.offset + lastPage.limit
      }
      return undefined
    },
    initialPageParam: 0,
  })

  const allItems = data?.pages.flatMap((page: any) => page.items) || []
  const stats = data?.pages[0]?.stats || {}
  const topMaterialsChart = data?.pages[0]?.top_materials_chart || []
  const keywordChart = data?.pages[0]?.keyword_chart || []
  const uniqueCompanies: string[] = data?.pages[0]?.unique_companies || []
  const totalFiltered = data?.pages[0]?.total_filtered || 0
  const totalAll = data?.pages[0]?.total || 0

  // Top 10 keywords bar chart data
  const topKeywordsChart = useMemo(() => {
    if (!keywordChart.length) return []
    return keywordChart.slice(0, 10)
  }, [keywordChart])

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const applyFilters = (newFilters: typeof filters) => {
    setFilters(newFilters)
    setAppliedFilters(newFilters)
    const params = new URLSearchParams()
    params.set('tab', activeTab)
    Object.entries(newFilters).forEach(([key, value]) => {
      if (value && value !== 'all') params.set(key, value)
    })
    setSearchParams(params)
  }

  const handleApplyFilters = () => {
    applyFilters(filters)
  }

  const handleReset = () => {
    const base = { company: '', participated: '', search: '' }
    setFilters(base)
    setAppliedFilters(base)
    setExpandedRows(new Set())
    const params = new URLSearchParams()
    params.set('tab', activeTab)
    setSearchParams(params)
  }

  const handleTabChange = (tab: string) => {
    setActiveTab(tab)
    setExpandedRows(new Set())
    const params = new URLSearchParams()
    params.set('tab', tab)
    Object.entries(filters).forEach(([key, value]) => {
      if (value && value !== 'all') params.set(key, value)
    })
    setSearchParams(params)
  }

  const toggleExpand = (key: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const hasActiveFilters = !!(filters.company || filters.participated || filters.search)

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
  }, [hasNextPage, isFetchingNextPage, fetchNextPage, activeTab])

  return (
    <PageWrapper
      title="Material Insights"
      description="Analyze matched material codes and keywords across all RFPs."
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
          title="Unique Materials"
          value={stats.total_unique_materials || 0}
          icon={Package}
          className="stat-card-blue"
        />
        <StatCard
          title="Unique Keywords"
          value={stats.total_unique_keywords || 0}
          icon={Tag}
          className="stat-card-amber"
        />
        <StatCard
          title="RFPs with Matches"
          value={stats.total_rfps_with_matches || 0}
          icon={Layers}
          className="stat-card-emerald"
        />
        <StatCard
          title="Submitted RFPs"
          value={stats.submitted_rfp_count || 0}
          icon={Send}
          trend={`${stats.total_material_rfp_links || 0} material links, ${stats.total_keyword_rfp_links || 0} keyword links`}
          className="stat-card-rose"
        />
      </div>

      {/* Charts Section */}
      {(topMaterialsChart.length > 0 || topKeywordsChart.length > 0) && (
        <div className="mb-6">
          {/* Top Items Bar Chart - switches based on active tab */}
          {activeTab === 'materials' && topMaterialsChart.length > 0 && (
            <Card className="border-slate-200 shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-base font-semibold text-slate-700 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-indigo-500" />
                  Top 10 Materials by RFP Count
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    data={topMaterialsChart}
                    margin={{ top: 10, right: 10, left: 0, bottom: 40 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      dataKey="material"
                      tick={{ fontSize: 10, fill: '#64748b' }}
                      angle={-25}
                      textAnchor="end"
                      interval={0}
                      height={60}
                    />
                    <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                      formatter={(value: any, _name: any, props: any) => [
                        `${value} RFPs`,
                        props.payload?.description || 'Material',
                      ]}
                    />
                    <Bar
                      dataKey="rfp_count"
                      name="RFP Count"
                      fill="#6366f1"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {activeTab === 'keywords' && topKeywordsChart.length > 0 && (
            <Card className="border-slate-200 shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-base font-semibold text-slate-700 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-amber-500" />
                  Top 10 Keywords by RFP Count
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    data={topKeywordsChart}
                    margin={{ top: 10, right: 10, left: 0, bottom: 40 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis
                      dataKey="keyword"
                      tick={{ fontSize: 10, fill: '#64748b' }}
                      angle={-25}
                      textAnchor="end"
                      interval={0}
                      height={60}
                    />
                    <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                      formatter={(value: any) => [`${value} RFPs`, 'Keyword']}
                    />
                    <Bar
                      dataKey="rfp_count"
                      name="RFP Count"
                      fill="#f59e0b"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

        </div>
      )}

      {/* Tabs + Filters + Table */}
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <div className="flex items-center justify-between mb-4">
          <TabsList>
            <TabsTrigger value="materials" className="gap-1.5">
              <Package className="h-4 w-4" />
              Materials
              {stats.total_unique_materials ? (
                <Badge variant="secondary" className="ml-1 text-xs">{stats.total_unique_materials}</Badge>
              ) : null}
            </TabsTrigger>
            <TabsTrigger value="keywords" className="gap-1.5">
              <Tag className="h-4 w-4" />
              Keywords
              {stats.total_unique_keywords ? (
                <Badge variant="secondary" className="ml-1 text-xs">{stats.total_unique_keywords}</Badge>
              ) : null}
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Filters Card */}
        <Card className="mb-6 border-slate-200 shadow-sm">
          <CardHeader className="pb-4">
            <CardTitle className="text-base font-semibold text-slate-700 flex items-center gap-2">
              <Filter className="h-4 w-4 text-indigo-500" />
              Filters
              {hasActiveFilters && (
                <Badge variant="secondary" className="ml-2 text-xs">Active</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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
                <Label htmlFor="participated" className="text-slate-600 text-sm flex items-center gap-1.5">
                  <Send className="h-3.5 w-3.5" />
                  Participation
                </Label>
                <Select
                  value={filters.participated || 'all'}
                  onValueChange={(value) => handleFilterChange('participated', value === 'all' ? '' : value)}
                >
                  <SelectTrigger id="participated" className="bg-slate-50 border-slate-200 focus:bg-white">
                    <SelectValue placeholder="All" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="submitted">Submitted</SelectItem>
                    <SelectItem value="declined">Declined</SelectItem>
                    <SelectItem value="open">Open</SelectItem>
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
                    placeholder={activeTab === 'materials' ? 'Search material code or description...' : 'Search keyword...'}
                    value={filters.search}
                    onChange={(e) => handleFilterChange('search', e.target.value)}
                    className="pl-10 bg-slate-50 border-slate-200 focus:bg-white"
                    onKeyDown={(e) => e.key === 'Enter' && handleApplyFilters()}
                  />
                </div>
              </div>

              <div className="space-y-2 flex items-end gap-2">
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

            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-slate-500">
                Showing <span className="font-semibold text-slate-700">{allItems.length}</span> of{' '}
                <span className="font-semibold text-slate-700">{totalFiltered}</span> {activeTab}
                {totalFiltered !== totalAll && (
                  <span className="text-slate-400"> ({totalAll} total)</span>
                )}
              </p>
              {hasNextPage && (
                <p className="text-sm text-indigo-600 font-medium">Scroll down to load more...</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Materials Tab Content */}
        <TabsContent value="materials">
          <Card className="border-slate-200 shadow-sm overflow-hidden">
            <CardContent className="p-0">
              {isLoading ? (
                <div className="p-6 space-y-4">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="flex items-center gap-4">
                      <Skeleton className="h-10 w-8" />
                      <Skeleton className="h-10 w-28" />
                      <Skeleton className="h-10 flex-1" />
                      <Skeleton className="h-10 w-20" />
                      <Skeleton className="h-10 w-24" />
                    </div>
                  ))}
                </div>
              ) : allItems.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-500">
                  <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                    <Package className="h-8 w-8 text-slate-400" />
                  </div>
                  <p className="text-lg font-medium text-slate-600 mb-2">No materials found</p>
                  <p className="text-sm text-slate-400 mb-4">
                    No matched material codes found in any RFPs
                  </p>
                  {hasActiveFilters && (
                    <Button variant="outline" onClick={handleReset} className="border-slate-200">
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Clear Filters
                    </Button>
                  )}
                </div>
              ) : (
                <ScrollArea className="h-[560px]" ref={scrollRef}>
                  <Table>
                    <TableHeader className="sticky top-0 bg-slate-50/95 backdrop-blur-sm z-10">
                      <TableRow className="border-slate-200 hover:bg-slate-50/95">
                        <TableHead className="w-10"></TableHead>
                        <TableHead className="text-slate-600 font-semibold">Material Code</TableHead>
                        <TableHead className="text-slate-600 font-semibold">Description</TableHead>
                        <TableHead className="text-slate-600 font-semibold">RFP Count</TableHead>
                        <TableHead className="text-slate-600 font-semibold">Companies</TableHead>
                        <TableHead className="text-slate-600 font-semibold">Submitted</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {allItems.map((item: any) => (
                        <Fragment key={item.material_code}>
                          {/* Parent material row */}
                          <TableRow
                            className="cursor-pointer hover:bg-slate-50/80 transition-colors"
                            onClick={() => toggleExpand(item.material_code)}
                          >
                            <TableCell className="w-10">
                              {expandedRows.has(item.material_code) ? (
                                <ChevronDown className="h-4 w-4 text-indigo-500" />
                              ) : (
                                <ChevronRight className="h-4 w-4 text-slate-400" />
                              )}
                            </TableCell>
                            <TableCell className="font-mono font-medium text-indigo-600">
                              {item.material_code}
                            </TableCell>
                            <TableCell className="text-slate-600 max-w-[300px] truncate" title={item.material_description}>
                              {item.material_description}
                            </TableCell>
                            <TableCell>
                              <Badge variant="secondary" className="gap-1">
                                <Hash className="h-3 w-3" />
                                {item.rfp_count} RFPs
                              </Badge>
                            </TableCell>
                            <TableCell className="text-slate-600">
                              {item.companies?.length || 0} {(item.companies?.length || 0) === 1 ? 'company' : 'companies'}
                            </TableCell>
                            <TableCell>
                              {item.submitted_count > 0 ? (
                                <Badge className="gap-1 bg-emerald-100 text-emerald-700 border-emerald-200">
                                  <Send className="h-3 w-3" />
                                  {item.submitted_count}
                                </Badge>
                              ) : (
                                <span className="text-slate-400 text-sm">0</span>
                              )}
                            </TableCell>
                          </TableRow>

                          {/* Expanded RFP rows */}
                          {expandedRows.has(item.material_code) && item.rfps?.map((rfp: any, idx: number) => (
                            <TableRow
                              key={`${item.material_code}-${rfp.rfp_id}-${idx}`}
                              className="bg-slate-50/60 border-l-3 border-l-indigo-300"
                            >
                              <TableCell></TableCell>
                              <TableCell className="pl-6 font-medium text-slate-700">
                                {rfp.rfp_id}
                              </TableCell>
                              <TableCell className="text-slate-500">{rfp.company}</TableCell>
                              <TableCell className="text-slate-500 text-sm">{rfp.rfp_end_date}</TableCell>
                              <TableCell>
                                <Badge variant="outline" className="text-xs">
                                  {rfp.match_method === 'exact' ? 'Exact' : 'Keyword'}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                {['submitted', 'yes'].includes(rfp.participated) ? (
                                  <Badge className="gap-1 bg-emerald-100 text-emerald-700 border-emerald-200 text-xs">
                                    <CheckCircle2 className="h-3 w-3" />
                                    Submitted
                                  </Badge>
                                ) : rfp.participated === 'declined' ? (
                                  <Badge variant="destructive" className="gap-1 text-xs">
                                    <XCircle className="h-3 w-3" />
                                    Declined
                                  </Badge>
                                ) : (
                                  <Badge variant="outline" className="gap-1 text-slate-500 text-xs">
                                    Open
                                  </Badge>
                                )}
                              </TableCell>
                            </TableRow>
                          ))}
                        </Fragment>
                      ))}
                      {isFetchingNextPage && (
                        <TableRow>
                          <TableCell colSpan={6} className="text-center py-8">
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
        </TabsContent>

        {/* Keywords Tab Content */}
        <TabsContent value="keywords">
          <Card className="border-slate-200 shadow-sm overflow-hidden">
            <CardContent className="p-0">
              {isLoading ? (
                <div className="p-6 space-y-4">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="flex items-center gap-4">
                      <Skeleton className="h-10 w-8" />
                      <Skeleton className="h-10 w-28" />
                      <Skeleton className="h-10 flex-1" />
                      <Skeleton className="h-10 w-20" />
                    </div>
                  ))}
                </div>
              ) : allItems.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-500">
                  <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
                    <Tag className="h-8 w-8 text-slate-400" />
                  </div>
                  <p className="text-lg font-medium text-slate-600 mb-2">No keywords found</p>
                  <p className="text-sm text-slate-400 mb-4">
                    No keyword-matched items found in any RFPs
                  </p>
                  {hasActiveFilters && (
                    <Button variant="outline" onClick={handleReset} className="border-slate-200">
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Clear Filters
                    </Button>
                  )}
                </div>
              ) : (
                <ScrollArea className="h-[560px]" ref={scrollRef}>
                  <Table>
                    <TableHeader className="sticky top-0 bg-slate-50/95 backdrop-blur-sm z-10">
                      <TableRow className="border-slate-200 hover:bg-slate-50/95">
                        <TableHead className="w-10"></TableHead>
                        <TableHead className="text-slate-600 font-semibold">Keyword</TableHead>
                        <TableHead className="text-slate-600 font-semibold">RFP Count</TableHead>
                        <TableHead className="text-slate-600 font-semibold">Material Codes</TableHead>
                        <TableHead className="text-slate-600 font-semibold">Companies</TableHead>
                        <TableHead className="text-slate-600 font-semibold">Submitted</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {allItems.map((item: any) => (
                        <Fragment key={`kw-${item.keyword}`}>
                          {/* Parent keyword row */}
                          <TableRow
                            className="cursor-pointer hover:bg-slate-50/80 transition-colors"
                            onClick={() => toggleExpand(`kw-${item.keyword}`)}
                          >
                            <TableCell className="w-10">
                              {expandedRows.has(`kw-${item.keyword}`) ? (
                                <ChevronDown className="h-4 w-4 text-amber-500" />
                              ) : (
                                <ChevronRight className="h-4 w-4 text-slate-400" />
                              )}
                            </TableCell>
                            <TableCell className="font-semibold text-amber-700">
                              <div className="flex items-center gap-2">
                                <Tag className="h-4 w-4 text-amber-500" />
                                {item.keyword}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant="secondary" className="gap-1">
                                <Hash className="h-3 w-3" />
                                {item.rfp_count} RFPs
                              </Badge>
                            </TableCell>
                            <TableCell className="text-slate-600">
                              {item.material_codes?.length || 0} codes
                            </TableCell>
                            <TableCell className="text-slate-600">
                              {item.companies?.length || 0} {(item.companies?.length || 0) === 1 ? 'company' : 'companies'}
                            </TableCell>
                            <TableCell>
                              {item.submitted_count > 0 ? (
                                <Badge className="gap-1 bg-emerald-100 text-emerald-700 border-emerald-200">
                                  <Send className="h-3 w-3" />
                                  {item.submitted_count}
                                </Badge>
                              ) : (
                                <span className="text-slate-400 text-sm">0</span>
                              )}
                            </TableCell>
                          </TableRow>

                          {/* Expanded RFP rows */}
                          {expandedRows.has(`kw-${item.keyword}`) && item.rfps?.map((rfp: any, idx: number) => (
                            <TableRow
                              key={`kw-${item.keyword}-${rfp.rfp_id}-${idx}`}
                              className="bg-amber-50/40 border-l-3 border-l-amber-300"
                            >
                              <TableCell></TableCell>
                              <TableCell className="pl-6 font-medium text-slate-700">
                                {rfp.rfp_id}
                              </TableCell>
                              <TableCell className="text-slate-500">{rfp.company}</TableCell>
                              <TableCell className="font-mono text-xs text-slate-500">
                                {rfp.material_code}
                              </TableCell>
                              <TableCell className="text-slate-500 text-sm max-w-[200px] truncate" title={rfp.material_description}>
                                {rfp.material_description}
                              </TableCell>
                              <TableCell>
                                {['submitted', 'yes'].includes(rfp.participated) ? (
                                  <Badge className="gap-1 bg-emerald-100 text-emerald-700 border-emerald-200 text-xs">
                                    <CheckCircle2 className="h-3 w-3" />
                                    Submitted
                                  </Badge>
                                ) : rfp.participated === 'declined' ? (
                                  <Badge variant="destructive" className="gap-1 text-xs">
                                    <XCircle className="h-3 w-3" />
                                    Declined
                                  </Badge>
                                ) : (
                                  <Badge variant="outline" className="gap-1 text-slate-500 text-xs">
                                    Open
                                  </Badge>
                                )}
                              </TableCell>
                            </TableRow>
                          ))}
                        </Fragment>
                      ))}
                      {isFetchingNextPage && (
                        <TableRow>
                          <TableCell colSpan={6} className="text-center py-8">
                            <div className="flex items-center justify-center gap-2">
                              <div className="w-5 h-5 border-3 border-slate-200 border-t-amber-600 rounded-full animate-spin" />
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
        </TabsContent>
      </Tabs>
    </PageWrapper>
  )
}
