import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  CheckCircle2,
  XCircle,
  Search,
  Tag,
  Hash,
  FileText,
} from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { api } from '@/lib/api'

type MaterialFilter = 'all' | 'matched' | 'not_matched'

interface MaterialBreakdownDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  rfpId: string | null
  company?: string | null
}

export function MaterialBreakdownDialog({
  open,
  onOpenChange,
  rfpId,
  company,
}: MaterialBreakdownDialogProps) {
  const [filter, setFilter] = useState<MaterialFilter>('all')
  const [search, setSearch] = useState('')

  // Reset state when dialog opens with new RFP
  useEffect(() => {
    if (open) {
      setFilter('all')
      setSearch('')
    }
  }, [open, rfpId])

  const { data, isLoading, isError } = useQuery({
    queryKey: ['rfpMaterials', rfpId, company],
    queryFn: () => api.getRfpMaterials(rfpId!, company || undefined),
    enabled: open && !!rfpId,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  })

  const materials = data?.materials || []
  const totalMaterials = data?.total_materials || 0
  const matchedCount = data?.matched_count || 0
  const matchPercentage = data?.match_percentage || 0

  // Apply filters
  const filteredMaterials = materials.filter((mat) => {
    if (filter === 'matched' && !mat.is_matched) return false
    if (filter === 'not_matched' && mat.is_matched) return false
    if (search) {
      const q = search.toLowerCase()
      return (
        (mat.material_code || '').toLowerCase().includes(q) ||
        (mat.bahra_item_code || '').toLowerCase().includes(q) ||
        (mat.name || '').toLowerCase().includes(q) ||
        (mat.description || '').toLowerCase().includes(q) ||
        (mat.master_description || '').toLowerCase().includes(q)
      )
    }
    return true
  })

  const getPercentageColor = (pct: number) => {
    if (pct >= 80) return 'text-emerald-700 bg-emerald-50'
    if (pct >= 50) return 'text-amber-700 bg-amber-50'
    return 'text-rose-700 bg-rose-50'
  }

  const getProgressColor = (pct: number) => {
    if (pct >= 80) return '[&>div]:bg-emerald-500'
    if (pct >= 50) return '[&>div]:bg-amber-500'
    return '[&>div]:bg-rose-500'
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold text-slate-800">
            Material Breakdown — {rfpId}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Detailed material matching breakdown for RFP {rfpId}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-4 py-4">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : isError ? (
          <div className="text-center py-8 text-slate-500">
            <p>Failed to load material data. Please try again.</p>
          </div>
        ) : (
          <>
            {/* Summary Header */}
            <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/50">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <span className="text-sm text-slate-500">Match Score</span>
                  <div className="flex items-baseline gap-2 mt-0.5">
                    <span className={`text-2xl font-bold px-2 py-0.5 rounded-lg ${getPercentageColor(matchPercentage)}`}>
                      {matchPercentage}%
                    </span>
                    <span className="text-sm text-slate-500">
                      {matchedCount} of {totalMaterials} materials matched
                    </span>
                  </div>
                </div>
                <div className="flex gap-3 text-center">
                  <div className="px-3 py-1.5 rounded-lg bg-emerald-50">
                    <p className="text-lg font-bold text-emerald-700">{matchedCount}</p>
                    <p className="text-xs text-emerald-600">Matched</p>
                  </div>
                  <div className="px-3 py-1.5 rounded-lg bg-rose-50">
                    <p className="text-lg font-bold text-rose-700">{totalMaterials - matchedCount}</p>
                    <p className="text-xs text-rose-600">Unmatched</p>
                  </div>
                </div>
              </div>
              <Progress
                value={matchPercentage}
                className={`h-2.5 bg-slate-200 ${getProgressColor(matchPercentage)}`}
              />
            </div>

            {/* Filter Tabs + Search */}
            <div className="flex items-center gap-3">
              <div className="flex rounded-lg border border-slate-200 overflow-hidden">
                {([
                  { key: 'all', label: 'All', count: totalMaterials },
                  { key: 'matched', label: 'Matched', count: matchedCount },
                  { key: 'not_matched', label: 'Not Matched', count: totalMaterials - matchedCount },
                ] as const).map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setFilter(tab.key)}
                    className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                      filter === tab.key
                        ? 'bg-indigo-600 text-white'
                        : 'bg-white text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {tab.label} ({tab.count})
                  </button>
                ))}
              </div>
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                <Input
                  placeholder="Search materials..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-8 h-8 text-sm bg-slate-50 border-slate-200"
                />
              </div>
            </div>

            {/* Materials Table */}
            <div className="flex-1 max-h-[380px] border border-slate-200 rounded-lg overflow-auto">
              <table className="min-w-full caption-bottom text-sm">
                <TableHeader className="sticky top-0 bg-slate-50/95 backdrop-blur-sm z-10">
                  <TableRow className="border-slate-200">
                    <TableHead className="text-slate-600 font-semibold w-[130px]">
                      <span className="flex items-center gap-1">
                        <Hash className="h-3.5 w-3.5" />
                        Code
                      </span>
                    </TableHead>
                    <TableHead className="text-slate-600 font-semibold w-[150px]">
                      <span className="flex items-center gap-1">
                        <Hash className="h-3.5 w-3.5" />
                        Bahra Item Code
                      </span>
                    </TableHead>
                    <TableHead className="text-slate-600 font-semibold min-w-[350px]">
                      <span className="flex items-center gap-1">
                        <FileText className="h-3.5 w-3.5" />
                        Description
                      </span>
                    </TableHead>
                    <TableHead className="text-slate-600 font-semibold w-[100px]">Status</TableHead>
                    <TableHead className="text-slate-600 font-semibold w-[110px]">
                      <span className="flex items-center gap-1">
                        <Tag className="h-3.5 w-3.5" />
                        Method
                      </span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredMaterials.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-slate-400">
                        No materials found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredMaterials.map((mat, idx) => (
                      <TableRow
                        key={`${mat.material_code}-${idx}`}
                        className={`border-slate-100 ${
                          mat.is_matched
                            ? 'bg-emerald-50/30 hover:bg-emerald-50/50'
                            : 'bg-rose-50/20 hover:bg-rose-50/40'
                        }`}
                      >
                        <TableCell className="font-mono text-sm font-medium text-slate-700">
                          {mat.material_code}
                        </TableCell>
                        <TableCell className="font-mono text-sm text-slate-700">
                          {mat.bahra_item_code || <span className="text-slate-400">—</span>}
                        </TableCell>
                        <TableCell className="text-sm text-slate-600">
                          {mat.master_description || mat.description || '-'}
                        </TableCell>
                        <TableCell>
                          {mat.is_matched ? (
                            <Badge variant="success" className="gap-1 text-xs">
                              <CheckCircle2 className="h-3 w-3" />
                              Matched
                            </Badge>
                          ) : (
                            <Badge variant="destructive" className="gap-1 text-xs">
                              <XCircle className="h-3 w-3" />
                              No Match
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          {mat.match_method ? (
                            <Badge
                              variant={mat.match_method === 'exact_code' ? 'info' : 'warning'}
                              className="text-xs"
                            >
                              {mat.match_method === 'exact_code' ? 'Exact' : mat.match_method === 'keyword' ? 'Keyword' : mat.match_method}
                            </Badge>
                          ) : (
                            <span className="text-slate-400 text-xs">—</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </table>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
