import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  BarChart3,
  TrendingUp,
  PieChart,
  Activity,
} from 'lucide-react'
import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { useHasPermission } from '@/hooks/use-auth'

// Simple chart components using CSS
function BarChartComponent({
  data,
  title,
  onBarClick
}: {
  data: { label: string; value: number; color: string }[];
  title: string;
  onBarClick?: (label: string, value: number) => void;
}) {
  const maxValue = Math.max(...data.map(d => d.value))

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-semibold text-slate-700">{title}</h4>
      <div className="space-y-2">
        {data.map((item, index) => (
          <div
            key={index}
            className={`flex items-center gap-3 ${onBarClick ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}`}
            onClick={() => onBarClick?.(item.label, item.value)}
            title={onBarClick ? `Click to drill down into ${item.label} RFPs` : item.label}
          >
            <div className="w-32 text-sm text-slate-600 truncate">
              {item.label}
            </div>
            <div className="flex-1 h-8 bg-slate-100 rounded-md overflow-hidden relative">
              <div
                className="h-full rounded-md transition-all duration-500 flex items-center justify-end pr-2"
                style={{
                  width: `${(item.value / maxValue) * 100}%`,
                  backgroundColor: item.color,
                  minWidth: item.value > 0 ? '30px' : '0px'
                }}
              >
                <span className="text-xs font-semibold text-white">{item.value}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function DonutChartComponent({
  data,
  title,
  onSegmentClick
}: {
  data: { label: string; value: number; color: string }[];
  title: string;
  onSegmentClick?: (label: string, value: number) => void;
}) {
  const total = data.reduce((sum, item) => sum + item.value, 0)

  return (
    <div className="space-y-4">
      <h4 className="text-sm font-semibold text-slate-700">{title}</h4>
      <div className="flex items-center justify-center">
        <div className="relative w-48 h-48">
          {/* Simple pie representation using gradients */}
          <div
            className="w-full h-full rounded-full"
            style={{
              background: `conic-gradient(${data.map((item, i) => {
                const prevSum = data.slice(0, i).reduce((s, d) => s + d.value, 0)
                const startPercent = (prevSum / total) * 100
                const endPercent = ((prevSum + item.value) / total) * 100
                return `${item.color} ${startPercent}% ${endPercent}%`
              }).join(', ')})`
            }}
          >
            {/* Center hole for donut */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="w-28 h-28 bg-white rounded-full flex items-center justify-center flex-col">
                <div className="text-2xl font-bold text-slate-800">{total}</div>
                <div className="text-xs text-slate-500">Total RFPs</div>
              </div>
            </div>
          </div>
        </div>
      </div>
      {onSegmentClick && (
        <p className="text-xs text-center text-slate-500 italic">Click on items below to drill down</p>
      )}
      <div className="space-y-2">
        {data.map((item, index) => (
          <div
            key={index}
            className={`flex items-center justify-between ${onSegmentClick ? 'cursor-pointer hover:bg-slate-50 p-2 -mx-2 rounded-md transition-colors border border-transparent hover:border-slate-200' : ''}`}
            onClick={() => onSegmentClick?.(item.label, item.value)}
            title={onSegmentClick ? `Click to drill down into ${item.label} RFPs` : ''}
          >
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
              <span className="text-sm text-slate-600">{item.label}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-800">{item.value}</span>
              <span className="text-xs text-slate-500">({((item.value / total) * 100).toFixed(1)}%)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  className,
  onClick
}: {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ElementType
  trend?: { value: string; isPositive: boolean }
  className?: string
  onClick?: () => void
}) {
  return (
    <div
      className={`rounded-xl p-5 ${className} ${onClick ? 'cursor-pointer hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200' : ''}`}
      onClick={onClick}
      title={onClick ? `Click to view details` : ''}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-slate-600 mb-1">{title}</p>
          <p className="text-3xl font-bold text-slate-800 mb-1">{value}</p>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
          {trend && (
            <div className={`flex items-center gap-1 mt-2 text-xs font-medium ${trend.isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
              <TrendingUp className={`h-3 w-3 ${!trend.isPositive && 'rotate-180'}`} />
              {trend.value}
            </div>
          )}
        </div>
        <div className="w-12 h-12 rounded-lg bg-white/60 flex items-center justify-center">
          <Icon className="h-6 w-6 text-slate-600" />
        </div>
      </div>
    </div>
  )
}

export default function AnalyticsPage() {
  const hasPermission = useHasPermission('analytics.view')
  const navigate = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['rfpAnalytics'],
    queryFn: () => api.getRfpDetails({ limit: 10000 }), // Get all data for analytics
  })

  const rfps = data?.pages?.[0]?.rfps || data?.rfps || []

  // Calculate analytics
  const totalRfps = rfps.length
  const submittedCount = rfps.filter((r: any) => r.status_key === 'submitted').length
  const declinedCount = rfps.filter((r: any) => r.status_key === 'declined').length
  const openCount = rfps.filter((r: any) => r.status_key === 'open').length

  // Material matching analytics
  const materialMatched = rfps.filter((r: any) => (r.Material_Matched || '').toLowerCase() === 'yes').length
  const materialNotMatched = totalRfps - materialMatched

  // Keyword matching analytics
  const keywordMatched = rfps.filter((r: any) => (r.Keyword_Matched || '').toLowerCase() === 'yes').length
  const keywordNotMatched = totalRfps - keywordMatched

  // Company analytics
  const companyStats: Record<string, number> = {}
  rfps.forEach((rfp: any) => {
    const company = rfp.Company_Name || 'Unknown'
    companyStats[company] = (companyStats[company] || 0) + 1
  })

  const topCompanies = Object.entries(companyStats)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5)

  // Participation by company
  const participationByCompany: Record<string, { participated: number; notParticipated: number; declined: number }> = {}
  rfps.forEach((rfp: any) => {
    const company = rfp.Company_Name || 'Unknown'
    if (!participationByCompany[company]) {
      participationByCompany[company] = { participated: 0, notParticipated: 0, declined: 0 }
    }
    if (rfp.status_key === 'submitted') participationByCompany[company].participated++
    else if (rfp.status_key === 'declined') participationByCompany[company].declined++
    else participationByCompany[company].notParticipated++
  })

  const participationRate = totalRfps > 0 ? ((submittedCount / totalRfps) * 100).toFixed(1) : '0'

  const statusData = [
    { label: 'Submitted', value: submittedCount, color: '#10b981' },
    { label: 'Open', value: openCount, color: '#f59e0b' },
    { label: 'Declined', value: declinedCount, color: '#ef4444' },
  ]

  const materialData = [
    { label: 'Material Matched', value: materialMatched, color: '#6366f1' },
    { label: 'Material Not Matched', value: materialNotMatched, color: '#94a3b8' },
  ]

  const keywordData = [
    { label: 'Keyword Matched', value: keywordMatched, color: '#8b5cf6' },
    { label: 'Keyword Not Matched', value: keywordNotMatched, color: '#cbd5e1' },
  ]

  const companyData = topCompanies.map(([company, count], index) => ({
    label: company,
    value: count,
    color: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'][index % 5]
  }))

  // Drill-down handlers
  const handleStatusClick = (statusLabel: string) => {
    const statusMap: Record<string, string> = {
      'Submitted': 'submitted',
      'Open': 'open',
      'Declined': 'declined',
    }
    const statusValue = statusMap[statusLabel] || statusLabel.toLowerCase()
    navigate(`/dashboard/rfp-insights?status=${statusValue}`)
  }

  const handleCompanyClick = (company: string) => {
    navigate(`/dashboard/rfp-insights?company=${encodeURIComponent(company)}`)
  }

  const handleMaterialMatchClick = (label: string) => {
    const materialValue = label === 'Material Matched' ? 'matched' : 'not_matched'
    navigate(`/dashboard/rfp-insights?material_match=${materialValue}`)
  }

  const handleKeywordMatchClick = (label: string) => {
    const keywordValue = label === 'Keyword Matched' ? 'matched' : 'not_matched'
    navigate(`/dashboard/rfp-insights?keyword_match=${keywordValue}`)
  }

  const handleParticipationClick = (company: string, participationType: 'participated' | 'notParticipated' | 'declined') => {
    const participationMap = {
      participated: 'participated',
      notParticipated: 'not_participated',
      declined: 'declined'
    }
    navigate(`/dashboard/rfp-insights?company=${encodeURIComponent(company)}&participation=${participationMap[participationType]}`)
  }

  if (!hasPermission) return null

  return (
    <PageWrapper
      title="Analytics Dashboard"
      description="Comprehensive insights and analytics for your RFP data"
      actions={
        <Button variant="outline" asChild className="border-slate-200 hover:bg-slate-50">
          <Link to="/dashboard">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Dashboard
          </Link>
        </Button>
      }
    >
      {isLoading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-96" />
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Total RFPs"
              value={totalRfps}
              subtitle="All downloaded RFPs"
              icon={BarChart3}
              className="stat-card-blue"
              onClick={() => navigate('/dashboard/rfp-insights')}
            />
            <StatCard
              title="Submitted"
              value={submittedCount}
              subtitle={`${participationRate}% participation rate`}
              icon={Activity}
              className="stat-card-emerald"
              onClick={() => handleStatusClick('Submitted')}
            />
            <StatCard
              title="Material Matched"
              value={materialMatched}
              subtitle={`${((materialMatched / totalRfps) * 100).toFixed(1)}% of total`}
              icon={PieChart}
              className="stat-card-violet"
              onClick={() => handleMaterialMatchClick('Material Matched')}
            />
            <StatCard
              title="Keyword Matched"
              value={keywordMatched}
              subtitle={`${((keywordMatched / totalRfps) * 100).toFixed(1)}% of total`}
              icon={TrendingUp}
              className="stat-card-amber"
              onClick={() => handleKeywordMatchClick('Keyword Matched')}
            />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Status Distribution */}
            <Card className="border-slate-200 shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg font-semibold text-slate-800">RFP Status Distribution</CardTitle>
                <CardDescription>Overview of RFP statuses (click to drill down)</CardDescription>
              </CardHeader>
              <CardContent>
                <DonutChartComponent
                  data={statusData}
                  title=""
                  onSegmentClick={handleStatusClick}
                />
              </CardContent>
            </Card>

            {/* Top Companies */}
            <Card className="border-slate-200 shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg font-semibold text-slate-800">Top Companies by RFP Count</CardTitle>
                <CardDescription>Companies with most RFPs (click to drill down)</CardDescription>
              </CardHeader>
              <CardContent>
                <BarChartComponent
                  data={companyData}
                  title=""
                  onBarClick={handleCompanyClick}
                />
              </CardContent>
            </Card>

            {/* Material Matching */}
            <Card className="border-slate-200 shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg font-semibold text-slate-800">Material Matching Analysis</CardTitle>
                <CardDescription>RFPs with material matches (click to drill down)</CardDescription>
              </CardHeader>
              <CardContent>
                <DonutChartComponent
                  data={materialData}
                  title=""
                  onSegmentClick={handleMaterialMatchClick}
                />
              </CardContent>
            </Card>

            {/* Keyword Matching */}
            <Card className="border-slate-200 shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg font-semibold text-slate-800">Keyword Matching Analysis</CardTitle>
                <CardDescription>RFPs with keyword matches (click to drill down)</CardDescription>
              </CardHeader>
              <CardContent>
                <DonutChartComponent
                  data={keywordData}
                  title=""
                  onSegmentClick={handleKeywordMatchClick}
                />
              </CardContent>
            </Card>
          </div>

          {/* Participation by Company */}
          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg font-semibold text-slate-800">Participation by Company</CardTitle>
              <CardDescription>Breakdown of participation status for each company (click segments to drill down)</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {Object.entries(participationByCompany)
                  .sort(([, a], [, b]) => (b.participated + b.notParticipated + b.declined) - (a.participated + a.notParticipated + a.declined))
                  .slice(0, 5)
                  .map(([company, stats]) => {
                    const total = stats.participated + stats.notParticipated + stats.declined
                    return (
                      <div key={company} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-slate-700">{company}</span>
                          <span className="text-xs text-slate-500">{total} RFPs</span>
                        </div>
                        <div className="flex h-6 rounded-md overflow-hidden">
                          {stats.participated > 0 && (
                            <div
                              className="bg-emerald-500 flex items-center justify-center text-xs text-white font-medium cursor-pointer hover:opacity-80 transition-opacity"
                              style={{ width: `${(stats.participated / total) * 100}%` }}
                              title={`Click to view ${stats.participated} participated RFPs for ${company}`}
                              onClick={() => handleParticipationClick(company, 'participated')}
                            >
                              {stats.participated > 0 && <span>{stats.participated}</span>}
                            </div>
                          )}
                          {stats.notParticipated > 0 && (
                            <div
                              className="bg-amber-500 flex items-center justify-center text-xs text-white font-medium cursor-pointer hover:opacity-80 transition-opacity"
                              style={{ width: `${(stats.notParticipated / total) * 100}%` }}
                              title={`Click to view ${stats.notParticipated} not participated RFPs for ${company}`}
                              onClick={() => handleParticipationClick(company, 'notParticipated')}
                            >
                              {stats.notParticipated > 0 && <span>{stats.notParticipated}</span>}
                            </div>
                          )}
                          {stats.declined > 0 && (
                            <div
                              className="bg-red-500 flex items-center justify-center text-xs text-white font-medium cursor-pointer hover:opacity-80 transition-opacity"
                              style={{ width: `${(stats.declined / total) * 100}%` }}
                              title={`Click to view ${stats.declined} declined RFPs for ${company}`}
                              onClick={() => handleParticipationClick(company, 'declined')}
                            >
                              {stats.declined > 0 && <span>{stats.declined}</span>}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-xs text-slate-600">
                          <div
                            className="flex items-center gap-1 cursor-pointer hover:text-emerald-600 transition-colors"
                            onClick={() => handleParticipationClick(company, 'participated')}
                            title="Click to filter"
                          >
                            <div className="w-2 h-2 rounded-full bg-emerald-500" />
                            <span>Participated: {stats.participated}</span>
                          </div>
                          <div
                            className="flex items-center gap-1 cursor-pointer hover:text-amber-600 transition-colors"
                            onClick={() => handleParticipationClick(company, 'notParticipated')}
                            title="Click to filter"
                          >
                            <div className="w-2 h-2 rounded-full bg-amber-500" />
                            <span>Not Participated: {stats.notParticipated}</span>
                          </div>
                          <div
                            className="flex items-center gap-1 cursor-pointer hover:text-red-600 transition-colors"
                            onClick={() => handleParticipationClick(company, 'declined')}
                            title="Click to filter"
                          >
                            <div className="w-2 h-2 rounded-full bg-red-500" />
                            <span>Declined: {stats.declined}</span>
                          </div>
                        </div>
                      </div>
                    )
                  })}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </PageWrapper>
  )
}
