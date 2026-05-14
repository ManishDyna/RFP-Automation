import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { ArrowDown, ArrowUp, Columns3, Database, Eye, Lock, Pencil, Plus, Search, Trash2, Upload } from 'lucide-react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { useHasPermission } from '@/hooks/use-auth'

// ─── Schemas ─────────────────────────────────────────────────────────────────

const materialSchema = z.object({
  material_code: z.string().min(1, 'Material code is required').max(100),
  description: z.string().max(2000).optional(),
})
type MaterialForm = z.infer<typeof materialSchema>

const keywordSchema = z.object({
  keyword: z.string().min(1, 'Keyword is required').max(500),
})
type KeywordForm = z.infer<typeof keywordSchema>

const columnSchema = z.object({
  column_key: z.string()
    .min(1, 'Key is required')
    .max(100)
    .regex(/^[a-z][a-z0-9_]*$/, 'Lowercase letters, numbers, underscores only. Must start with a letter.'),
  column_label: z.string().min(1, 'Label is required').max(200),
  column_type: z.enum(['text', 'dropdown', 'yes_no', 'button']),
  column_category: z.enum(['display', 'input']),
  sort_order: z.string().optional(),
  dropdown_options: z.string().optional(),
  button_url: z.string().optional(),
  is_required: z.boolean().optional(),
})
type ColumnForm = z.infer<typeof columnSchema>

// ─── Import Dialog ────────────────────────────────────────────────────────────

interface ImportDialogProps {
  open: boolean
  onClose: () => void
  type: 'materials' | 'keywords' | 'rfp_team'
  onImport: (file: File) => Promise<void>
  isPending: boolean
}

function ImportDialog({ open, onClose, type, onImport, isPending }: ImportDialogProps) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const handleClose = () => {
    setSelectedFile(null)
    if (fileRef.current) fileRef.current.value = ''
    onClose()
  }

  const handleSubmit = async () => {
    if (!selectedFile) return
    await onImport(selectedFile)
    handleClose()
  }

  const hint =
    type === 'materials'
      ? 'Required column: material_code. Optional: description.'
      : type === 'keywords'
        ? 'Required column: keyword (or the first column is used).'
        : 'Required columns: product, name, email.'

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            Import {type === 'materials' ? 'Material Codes' : type === 'keywords' ? 'Keywords' : 'RFP Team Members'}
          </DialogTitle>
          <DialogDescription>{hint}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1">
            <Label>File (.csv, .xlsx, .xls)</Label>
            <Input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
            />
          </div>
          {selectedFile && (
            <p className="text-sm text-muted-foreground">
              Selected: <span className="font-medium">{selectedFile.name}</span>
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={!selectedFile || isPending} loading={isPending}>
            <Upload className="h-4 w-4 mr-2" />
            Import
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── Materials Tab ────────────────────────────────────────────────────────────

function MaterialsTab() {
  const queryClient = useQueryClient()
  const canCreate = useHasPermission('material_master.create')
  const canEdit   = useHasPermission('material_master.edit')
  const canDelete = useHasPermission('material_master.delete')

  const [search, setSearch]             = useState('')
  const [dialogOpen, setDialogOpen]     = useState(false)
  const [editingItem, setEditingItem]   = useState<any>(null)
  const [deleteItem, setDeleteItem]     = useState<any>(null)
  const [importOpen, setImportOpen]     = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['materials', search],
    queryFn: () => api.getMaterials({ search: search || undefined, page_size: 500 }),
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<MaterialForm>({ resolver: zodResolver(materialSchema) })

  const closeDialog = () => {
    setDialogOpen(false)
    setEditingItem(null)
    reset()
  }

  const openAdd = () => {
    setEditingItem(null)
    reset({ material_code: '', description: '' })
    setDialogOpen(true)
  }

  const openEdit = (item: any) => {
    setEditingItem(item)
    reset({ material_code: item.material_code ?? '', description: item.description ?? '' })
    setDialogOpen(true)
  }

  const saveMutation = useMutation({
    mutationFn: (formData: MaterialForm) =>
      editingItem
        ? api.updateMaterial(editingItem.record_id, formData)
        : api.createMaterial(formData),
    onSuccess: () => {
      toast.success(editingItem ? 'Material updated' : 'Material created')
      queryClient.invalidateQueries({ queryKey: ['materials'] })
      closeDialog()
    },
    onError: (err: any) => toast.error(err.message || 'Operation failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteMaterial(id),
    onSuccess: () => {
      toast.success('Material deleted')
      queryClient.invalidateQueries({ queryKey: ['materials'] })
      setDeleteItem(null)
    },
    onError: (err: any) => toast.error(err.message || 'Delete failed'),
  })

  const importMutation = useMutation({
    mutationFn: (file: File) => api.importMaterials(file),
    onSuccess: (res: any) => {
      queryClient.invalidateQueries({ queryKey: ['materials'] })
      toast.success(
        `Import complete — Created: ${res.created}, Skipped: ${res.skipped}, Failed: ${res.failed}`
      )
    },
    onError: (err: any) => toast.error(err.message || 'Import failed'),
  })

  const materials = data?.materials ?? []

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search material code or description…"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {canCreate && (
          <>
            <Button variant="outline" onClick={() => setImportOpen(true)}>
              <Upload className="h-4 w-4 mr-2" />
              Import
            </Button>
            <Button onClick={openAdd}>
              <Plus className="h-4 w-4 mr-2" />
              Add Material
            </Button>
          </>
        )}
      </div>

      {/* Count badge */}
      {!isLoading && (
        <p className="text-sm text-muted-foreground">
          {materials.length} material{materials.length !== 1 ? 's' : ''} found
        </p>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : materials.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Database className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p>No materials found. {canCreate ? 'Add one or import from a file.' : ''}</p>
        </div>
      ) : (
        <ScrollArea className="h-[calc(100vh-400px)]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[200px]">Material Code</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="w-[160px]">Created</TableHead>
                {(canEdit || canDelete) && <TableHead className="text-right w-[100px]">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {materials.map((item: any) => (
                <TableRow key={item.record_id}>
                  <TableCell className="font-mono font-medium">{item.material_code}</TableCell>
                  <TableCell className="text-muted-foreground max-w-[400px] truncate">
                    {item.description || <span className="italic opacity-50">—</span>}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {item.created_date ? item.created_date.slice(0, 10) : '—'}
                  </TableCell>
                  {(canEdit || canDelete) && (
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {canEdit && (
                          <Button variant="ghost" size="icon" onClick={() => openEdit(item)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                        )}
                        {canDelete && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setDeleteItem(item)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ScrollArea>
      )}

      {/* Add / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(o) => !o && closeDialog()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingItem ? 'Edit Material' : 'Add Material Code'}</DialogTitle>
            <DialogDescription>
              {editingItem ? 'Update the material code details.' : 'Add a new material code to the master list.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit((d) => saveMutation.mutate(d))} className="space-y-4">
            <div className="space-y-1">
              <Label>Material Code *</Label>
              <Input {...register('material_code')} placeholder="e.g. 123456789" />
              {errors.material_code && (
                <p className="text-xs text-destructive">{errors.material_code.message}</p>
              )}
            </div>
            <div className="space-y-1">
              <Label>Description</Label>
              <Input {...register('description')} placeholder="Optional description" />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={closeDialog}>Cancel</Button>
              <Button type="submit" loading={saveMutation.isPending}>
                {editingItem ? 'Save Changes' : 'Add Material'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteItem} onOpenChange={(o) => !o && setDeleteItem(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Material</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete material code{' '}
              <span className="font-mono font-semibold">{deleteItem?.material_code}</span>?
              This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteItem && deleteMutation.mutate(deleteItem.record_id)}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Import Dialog */}
      <ImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        type="materials"
        onImport={(file) => importMutation.mutateAsync(file)}
        isPending={importMutation.isPending}
      />
    </div>
  )
}

// ─── Keywords Tab ─────────────────────────────────────────────────────────────

function KeywordsTab() {
  const queryClient = useQueryClient()
  const canCreate = useHasPermission('keyword_master.create')
  const canEdit   = useHasPermission('keyword_master.edit')
  const canDelete = useHasPermission('keyword_master.delete')

  const [search, setSearch]           = useState('')
  const [dialogOpen, setDialogOpen]   = useState(false)
  const [editingItem, setEditingItem] = useState<any>(null)
  const [deleteItem, setDeleteItem]   = useState<any>(null)
  const [importOpen, setImportOpen]   = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['keywords', search],
    queryFn: () => api.getKeywords({ search: search || undefined, page_size: 1000 }),
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<KeywordForm>({ resolver: zodResolver(keywordSchema) })

  const closeDialog = () => {
    setDialogOpen(false)
    setEditingItem(null)
    reset()
  }

  const openAdd = () => {
    setEditingItem(null)
    reset({ keyword: '' })
    setDialogOpen(true)
  }

  const openEdit = (item: any) => {
    setEditingItem(item)
    reset({ keyword: item.keyword ?? '' })
    setDialogOpen(true)
  }

  const saveMutation = useMutation({
    mutationFn: (formData: KeywordForm) =>
      editingItem
        ? api.updateKeyword(editingItem.record_id, formData)
        : api.createKeyword(formData),
    onSuccess: () => {
      toast.success(editingItem ? 'Keyword updated' : 'Keyword created')
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      closeDialog()
    },
    onError: (err: any) => toast.error(err.message || 'Operation failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteKeyword(id),
    onSuccess: () => {
      toast.success('Keyword deleted')
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      setDeleteItem(null)
    },
    onError: (err: any) => toast.error(err.message || 'Delete failed'),
  })

  const importMutation = useMutation({
    mutationFn: (file: File) => api.importKeywords(file),
    onSuccess: (res: any) => {
      queryClient.invalidateQueries({ queryKey: ['keywords'] })
      toast.success(
        `Import complete — Created: ${res.created}, Skipped: ${res.skipped}, Failed: ${res.failed}`
      )
    },
    onError: (err: any) => toast.error(err.message || 'Import failed'),
  })

  const keywords = data?.keywords ?? []

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search keywords…"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {canCreate && (
          <>
            <Button variant="outline" onClick={() => setImportOpen(true)}>
              <Upload className="h-4 w-4 mr-2" />
              Import
            </Button>
            <Button onClick={openAdd}>
              <Plus className="h-4 w-4 mr-2" />
              Add Keyword
            </Button>
          </>
        )}
      </div>

      {!isLoading && (
        <p className="text-sm text-muted-foreground">
          {keywords.length} keyword{keywords.length !== 1 ? 's' : ''} found
        </p>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : keywords.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Database className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p>No keywords found. {canCreate ? 'Add one or import from a file.' : ''}</p>
        </div>
      ) : (
        <ScrollArea className="h-[calc(100vh-400px)]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Keyword</TableHead>
                <TableHead className="w-[160px]">Created</TableHead>
                {(canEdit || canDelete) && <TableHead className="text-right w-[100px]">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {keywords.map((item: any) => (
                <TableRow key={item.record_id}>
                  <TableCell>
                    <Badge variant="secondary" className="font-mono text-sm">
                      {item.keyword}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {item.created_date ? item.created_date.slice(0, 10) : '—'}
                  </TableCell>
                  {(canEdit || canDelete) && (
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {canEdit && (
                          <Button variant="ghost" size="icon" onClick={() => openEdit(item)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                        )}
                        {canDelete && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setDeleteItem(item)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ScrollArea>
      )}

      {/* Add / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(o) => !o && closeDialog()}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{editingItem ? 'Edit Keyword' : 'Add Keyword'}</DialogTitle>
            <DialogDescription>
              Keywords are stored in UPPERCASE and used to match RFP content.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit((d) => saveMutation.mutate(d))} className="space-y-4">
            <div className="space-y-1">
              <Label>Keyword *</Label>
              <Input {...register('keyword')} placeholder="e.g. CABLE" className="uppercase" />
              {errors.keyword && (
                <p className="text-xs text-destructive">{errors.keyword.message}</p>
              )}
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={closeDialog}>Cancel</Button>
              <Button type="submit" loading={saveMutation.isPending}>
                {editingItem ? 'Save Changes' : 'Add Keyword'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteItem} onOpenChange={(o) => !o && setDeleteItem(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Keyword</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete keyword{' '}
              <Badge variant="secondary" className="font-mono">{deleteItem?.keyword}</Badge>?
              This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteItem && deleteMutation.mutate(deleteItem.record_id)}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Import Dialog */}
      <ImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        type="keywords"
        onImport={(file) => importMutation.mutateAsync(file)}
        isPending={importMutation.isPending}
      />
    </div>
  )
}

// ─── RFP Team Tab (Dynamic Columns) ──────────────────────────────────────────

// Core fields that must always appear in the team member form/table
const RFP_TEAM_CORE_FIELDS = [
  { column_key: 'product', column_label: 'Products', column_type: 'text', column_category: 'display', sort_order: '1', is_required: 'true', is_team_field: 'true' },
  { column_key: 'name', column_label: 'Name', column_type: 'text', column_category: 'display', sort_order: '2', is_required: 'true', is_team_field: 'true' },
  { column_key: 'email', column_label: 'Email', column_type: 'text', column_category: 'display', sort_order: '3', is_required: 'true', is_team_field: 'true' },
]
const RFP_TEAM_CORE_KEYS = RFP_TEAM_CORE_FIELDS.map(f => f.column_key)

function RfpTeamTab() {
  const queryClient = useQueryClient()
  const canCreate = useHasPermission('rfp_team.create')
  const canEdit   = useHasPermission('rfp_team.edit')
  const canDelete = useHasPermission('rfp_team.delete')

  const [search, setSearch]           = useState('')
  const [dialogOpen, setDialogOpen]   = useState(false)
  const [editingItem, setEditingItem] = useState<any>(null)
  const [deleteItem, setDeleteItem]   = useState<any>(null)
  const [importOpen, setImportOpen]   = useState(false)
  const [formValues, setFormValues]   = useState<Record<string, string>>({})

  // Fetch column definitions
  const { data: colData } = useQuery({
    queryKey: ['rfp-team-columns-all'],
    queryFn: () => api.getAllRfpTeamColumns(),
  })
  const allColumns: any[] = colData?.columns ?? []
  // Team fields are shown in the add/edit dialog and table
  // Ensure core fields (product, name, email) are always present even if column definitions are misconfigured
  const teamFieldColumns = useMemo(() => {
    const filtered = allColumns.filter((c: any) => String(c.is_team_field).toLowerCase() === 'true')
    const existingKeys = new Set(filtered.map((c: any) => c.column_key))
    // Prepend any missing core fields
    const missing = RFP_TEAM_CORE_FIELDS.filter(f => !existingKeys.has(f.column_key))
    const merged = [...missing, ...filtered]
    // Sort: core fields first in order, then the rest
    merged.sort((a: any, b: any) => {
      const aCore = RFP_TEAM_CORE_KEYS.indexOf(a.column_key)
      const bCore = RFP_TEAM_CORE_KEYS.indexOf(b.column_key)
      if (aCore !== -1 && bCore !== -1) return aCore - bCore
      if (aCore !== -1) return -1
      if (bCore !== -1) return 1
      return parseInt(a.sort_order || '999') - parseInt(b.sort_order || '999')
    })
    return merged
  }, [allColumns])

  const { data, isLoading } = useQuery({
    queryKey: ['rfp-team', search],
    queryFn: () => api.getRfpTeam({ search: search || undefined, page_size: 500 }),
  })

  const closeDialog = () => {
    setDialogOpen(false)
    setEditingItem(null)
    setFormValues({})
  }

  const openAdd = () => {
    setEditingItem(null)
    const defaults: Record<string, string> = {}
    teamFieldColumns.forEach((col: any) => { defaults[col.column_key] = '' })
    setFormValues(defaults)
    setDialogOpen(true)
  }

  const openEdit = (item: any) => {
    setEditingItem(item)
    const vals: Record<string, string> = {}
    teamFieldColumns.forEach((col: any) => { vals[col.column_key] = item[col.column_key] ?? '' })
    setFormValues(vals)
    setDialogOpen(true)
  }

  const handleFormChange = (key: string, value: string) => {
    setFormValues((prev) => ({ ...prev, [key]: value }))
  }

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // Validate required fields
    for (const col of teamFieldColumns) {
      if (String(col.is_required).toLowerCase() === 'true' && !formValues[col.column_key]?.trim()) {
        toast.error(`${col.column_label} is required`)
        return
      }
    }
    // Validate email format if email field exists
    const emailVal = formValues['email']
    if (emailVal && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailVal)) {
      toast.error('Must be a valid email')
      return
    }
    saveMutation.mutate(formValues)
  }

  const saveMutation = useMutation({
    mutationFn: (formData: Record<string, string>) =>
      editingItem
        ? api.updateRfpTeamMember(editingItem.record_id, formData)
        : api.createRfpTeamMember(formData),
    onSuccess: () => {
      toast.success(editingItem ? 'Team member updated' : 'Team member created')
      queryClient.invalidateQueries({ queryKey: ['rfp-team'] })
      closeDialog()
    },
    onError: (err: any) => toast.error(err.message || 'Operation failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteRfpTeamMember(id),
    onSuccess: () => {
      toast.success('Team member deleted')
      queryClient.invalidateQueries({ queryKey: ['rfp-team'] })
      setDeleteItem(null)
    },
    onError: (err: any) => toast.error(err.message || 'Delete failed'),
  })

  const importMutation = useMutation({
    mutationFn: (file: File) => api.importRfpTeam(file),
    onSuccess: (res: any) => {
      queryClient.invalidateQueries({ queryKey: ['rfp-team'] })
      toast.success(
        `Import complete — Created: ${res.created}, Skipped: ${res.skipped}, Failed: ${res.failed}`
      )
    },
    onError: (err: any) => toast.error(err.message || 'Import failed'),
  })

  const members = data?.rfp_team ?? []

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search product, name, or email…"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {canCreate && (
          <>
            <Button variant="outline" onClick={() => setImportOpen(true)}>
              <Upload className="h-4 w-4 mr-2" />
              Import
            </Button>
            <Button onClick={openAdd}>
              <Plus className="h-4 w-4 mr-2" />
              Add Member
            </Button>
          </>
        )}
      </div>

      {/* Count */}
      {!isLoading && (
        <p className="text-sm text-muted-foreground">
          {members.length} team member{members.length !== 1 ? 's' : ''} found
        </p>
      )}

      {/* Table — dynamic columns */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : members.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Database className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p>No team members found. {canCreate ? 'Add one or import from a file.' : ''}</p>
        </div>
      ) : (
        <ScrollArea className="h-[calc(100vh-400px)]">
          <Table>
            <TableHeader>
              <TableRow>
                {teamFieldColumns.map((col: any) => (
                  <TableHead key={col.column_key}>{col.column_label}</TableHead>
                ))}
                <TableHead className="w-[120px]">Created</TableHead>
                {(canEdit || canDelete) && <TableHead className="text-right w-[100px]">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((item: any) => (
                <TableRow key={item.record_id}>
                  {teamFieldColumns.map((col: any) => (
                    <TableCell key={col.column_key} className={col.column_key === 'email' ? 'font-mono text-sm text-muted-foreground' : ''}>
                      {col.column_type === 'button'
                        ? <Badge variant="outline" className="text-xs">Button</Badge>
                        : (item[col.column_key] || <span className="italic opacity-50">—</span>)}
                    </TableCell>
                  ))}
                  <TableCell className="text-sm text-muted-foreground">
                    {item.created_date ? item.created_date.slice(0, 10) : '—'}
                  </TableCell>
                  {(canEdit || canDelete) && (
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {canEdit && (
                          <Button variant="ghost" size="icon" onClick={() => openEdit(item)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                        )}
                        {canDelete && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setDeleteItem(item)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ScrollArea>
      )}

      {/* Add / Edit Dialog — dynamic fields */}
      <Dialog open={dialogOpen} onOpenChange={(o) => !o && closeDialog()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingItem ? 'Edit Team Member' : 'Add Team Member'}</DialogTitle>
            <DialogDescription>
              {editingItem ? 'Update the team member details.' : 'Add a new RFP team member for product-based email routing.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleFormSubmit} className="space-y-4">
            {teamFieldColumns.filter((col: any) => col.column_type !== 'button').map((col: any) => {
              const isRequired = String(col.is_required).toLowerCase() === 'true'
              return (
                <div key={col.column_key} className="space-y-1">
                  <Label>{col.column_label}{isRequired ? ' *' : ''}</Label>
                  {col.column_type === 'dropdown' ? (
                    <Select
                      value={formValues[col.column_key] || ''}
                      onValueChange={(v) => handleFormChange(col.column_key, v)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={`Select ${col.column_label}`} />
                      </SelectTrigger>
                      <SelectContent>
                        {(() => {
                          try {
                            const opts = JSON.parse(col.dropdown_options || '[]')
                            return opts.map((opt: string) => (
                              <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                            ))
                          } catch {
                            return null
                          }
                        })()}
                      </SelectContent>
                    </Select>
                  ) : col.column_type === 'yes_no' ? (
                    <Select
                      value={formValues[col.column_key] || ''}
                      onValueChange={(v) => handleFormChange(col.column_key, v)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={`Select ${col.column_label}`} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Yes">Yes</SelectItem>
                        <SelectItem value="No">No</SelectItem>
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      type={col.column_key === 'email' ? 'email' : 'text'}
                      value={formValues[col.column_key] || ''}
                      onChange={(e) => handleFormChange(col.column_key, e.target.value)}
                      placeholder={`Enter ${col.column_label.toLowerCase()}`}
                    />
                  )}
                </div>
              )
            })}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={closeDialog}>Cancel</Button>
              <Button type="submit" loading={saveMutation.isPending}>
                {editingItem ? 'Save Changes' : 'Add Member'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteItem} onOpenChange={(o) => !o && setDeleteItem(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Team Member</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete{' '}
              <span className="font-semibold">{deleteItem?.name}</span> ({deleteItem?.product})?
              This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteItem && deleteMutation.mutate(deleteItem.record_id)}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Import Dialog */}
      <ImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        type="rfp_team"
        onImport={(file) => importMutation.mutateAsync(file)}
        isPending={importMutation.isPending}
      />
    </div>
  )
}

// ─── Column Config Tab ───────────────────────────────────────────────────────

function ColumnConfigTab() {
  const queryClient = useQueryClient()
  const canCreate = useHasPermission('column_config.create')
  const canEdit   = useHasPermission('column_config.edit')
  const canDelete = useHasPermission('column_config.delete')

  const [dialogOpen, setDialogOpen]     = useState(false)
  const [editingItem, setEditingItem]   = useState<any>(null)
  const [deleteItem, setDeleteItem]     = useState<any>(null)
  const [previewOpen, setPreviewOpen]   = useState(false)
  // UI-only mode for the Button column dialog. 'builtin' = wire to the upload
  // page (storage value forced to '{upload_url}'). 'custom' = admin-typed URL.
  const [buttonMode, setButtonMode]     = useState<'builtin' | 'custom'>('builtin')

  const { data, isLoading } = useQuery({
    queryKey: ['rfp-team-columns'],
    queryFn: () => api.getRfpTeamColumns({ page_size: 100 }),
  })

  // Fetch team members only when preview is open
  const { data: teamData, isLoading: teamLoading } = useQuery({
    queryKey: ['rfp-team-preview'],
    queryFn: () => api.getRfpTeam({ page_size: 500 }),
    enabled: previewOpen,
  })

  const {
    register,
    handleSubmit,
    reset,
    control,
    watch,
    setValue,
    formState: { errors },
  } = useForm<ColumnForm>({
    resolver: zodResolver(columnSchema),
    defaultValues: {
      column_type: 'text',
      column_category: 'display',
      is_required: false,
    },
  })

  const watchType = watch('column_type')

  // Button columns can only be Display (no value to collect). When the user
  // switches Type to Button, force category=display. The URL value comes from
  // the buttonMode picker below — we no longer auto-fill the input here.
  useEffect(() => {
    if (watchType === 'button') {
      setValue('column_category', 'display')
    }
  }, [watchType, setValue])

  const closeDialog = () => {
    setDialogOpen(false)
    setEditingItem(null)
    reset({
      column_key: '', column_label: '', column_type: 'text',
      column_category: 'display', sort_order: '', dropdown_options: '',
      button_url: '', is_required: false,
    })
  }

  const openAdd = () => {
    setEditingItem(null)
    setButtonMode('builtin')
    reset({
      column_key: '', column_label: '', column_type: 'text',
      column_category: 'display', sort_order: '', dropdown_options: '',
      button_url: '', is_required: false,
    })
    setDialogOpen(true)
  }

  const openEdit = (item: any) => {
    const ct = item.column_type ?? 'text'
    const savedUrl = item.dropdown_options ?? ''
    // Builtin mode iff the saved value is exactly '{upload_url}'.
    const mode: 'builtin' | 'custom' = ct === 'button' && savedUrl.trim() === '{upload_url}' ? 'builtin' : 'custom'
    setButtonMode(mode)
    reset({
      column_key: item.column_key ?? '',
      column_label: item.column_label ?? '',
      column_type: ct,
      column_category: item.column_category ?? 'display',
      sort_order: item.sort_order ?? '',
      dropdown_options: ct === 'button' ? '' : savedUrl,
      // In builtin mode the URL field is hidden, so leave button_url blank.
      // The save mutation will write '{upload_url}' for us.
      button_url: ct === 'button' && mode === 'custom' ? savedUrl : '',
      is_required: String(item.is_required).toLowerCase() === 'true',
    })
    setEditingItem(item)
    setDialogOpen(true)
  }

  const saveMutation = useMutation({
    mutationFn: (formData: ColumnForm) => {
      // Button URL is persisted in the dropdown_options field (no DB migration needed).
      // Builtin mode hides the URL input and writes '{upload_url}' so the server-side
      // resolver wires the button to the existing /upload page + SharePoint pipeline.
      const dropdownOptions = formData.column_type === 'button'
        ? (buttonMode === 'builtin'
            ? '{upload_url}'
            : (formData.button_url ?? '').trim())
        : (formData.dropdown_options ?? '')
      const payload: any = {
        column_key: formData.column_key,
        column_label: formData.column_label,
        column_type: formData.column_type,
        column_category: formData.column_category,
        sort_order: formData.sort_order,
        dropdown_options: dropdownOptions,
        is_required: formData.is_required ? 'true' : 'false',
      }
      return editingItem
        ? api.updateRfpTeamColumn(editingItem.record_id, payload)
        : api.createRfpTeamColumn(payload)
    },
    onSuccess: () => {
      toast.success(editingItem ? 'Column updated' : 'Column created')
      queryClient.invalidateQueries({ queryKey: ['rfp-team-columns'] })
      queryClient.invalidateQueries({ queryKey: ['rfp-team-columns-all'] })
      closeDialog()
    },
    onError: (err: any) => toast.error(err.message || 'Operation failed'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteRfpTeamColumn(id),
    onSuccess: () => {
      toast.success('Column deleted')
      queryClient.invalidateQueries({ queryKey: ['rfp-team-columns'] })
      queryClient.invalidateQueries({ queryKey: ['rfp-team-columns-all'] })
      setDeleteItem(null)
    },
    onError: (err: any) => toast.error(err.message || 'Delete failed'),
  })

  const reorderMutation = useMutation({
    mutationFn: (ids: string[]) => api.reorderRfpTeamColumns(ids),
    onSuccess: () => {
      toast.success('Column order updated')
      queryClient.invalidateQueries({ queryKey: ['rfp-team-columns'] })
      queryClient.invalidateQueries({ queryKey: ['rfp-team-columns-all'] })
    },
    onError: (err: any) => toast.error(err.message || 'Reorder failed'),
  })

  const columns: any[] = data?.columns ?? []

  const moveColumn = (index: number, direction: 'up' | 'down') => {
    const ordered = [...columns]
    const swapIdx = direction === 'up' ? index - 1 : index + 1
    if (swapIdx < 0 || swapIdx >= ordered.length) return
    ;[ordered[index], ordered[swapIdx]] = [ordered[swapIdx], ordered[index]]
    reorderMutation.mutate(ordered.map((c) => c.record_id))
  }

  const categoryLabel = (cat: string) =>
    cat === 'display' ? 'Display' : cat === 'input' ? 'Input' : cat

  const typeLabel = (t: string) =>
    t === 'text' ? 'Text'
    : t === 'dropdown' ? 'Dropdown'
    : t === 'yes_no' ? 'Yes/No'
    : t === 'button' ? 'Button'
    : t

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-sm text-muted-foreground">
          Define columns for RFP Team table, email cards, and response forms.
        </p>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setPreviewOpen(true)}>
            <Eye className="h-4 w-4 mr-2" />
            Preview Email
          </Button>
          {canCreate && (
            <Button onClick={openAdd}>
              <Plus className="h-4 w-4 mr-2" />
              Add Column
            </Button>
          )}
        </div>
      </div>

      {columns.length > 6 && (
        <div className="rounded-md border border-yellow-500/50 bg-yellow-500/10 p-3 text-sm text-yellow-700">
          You have {columns.length} columns. Adaptive Cards in Outlook have limited horizontal space — consider keeping it under 6 columns for best readability.
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : columns.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Columns3 className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p>No column definitions found. Add one to get started.</p>
        </div>
      ) : (
        <ScrollArea className="h-[calc(100vh-420px)]">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[60px]">Order</TableHead>
                <TableHead className="w-[140px]">Key</TableHead>
                <TableHead>Label</TableHead>
                <TableHead className="w-[100px]">Type</TableHead>
                <TableHead className="w-[100px]">Category</TableHead>
                <TableHead className="w-[80px]">Required</TableHead>
                {(canEdit || canDelete) && <TableHead className="text-right w-[140px]">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {columns.map((item: any, idx: number) => {
                const isProtected = String(item.is_protected).toLowerCase() === 'true'
                return (
                  <TableRow key={item.record_id}>
                    <TableCell>
                      <div className="flex gap-0.5">
                        {canEdit && (
                          <>
                            <Button variant="ghost" size="icon" className="h-6 w-6" disabled={idx === 0} onClick={() => moveColumn(idx, 'up')}>
                              <ArrowUp className="h-3 w-3" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-6 w-6" disabled={idx === columns.length - 1} onClick={() => moveColumn(idx, 'down')}>
                              <ArrowDown className="h-3 w-3" />
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {item.column_key}
                      {isProtected && <Lock className="inline ml-1 h-3 w-3 text-muted-foreground" />}
                    </TableCell>
                    <TableCell className="font-medium">{item.column_label}</TableCell>
                    <TableCell><Badge variant="outline">{typeLabel(item.column_type)}</Badge></TableCell>
                    <TableCell><Badge variant="secondary">{categoryLabel(item.column_category)}</Badge></TableCell>
                    <TableCell>{String(item.is_required).toLowerCase() === 'true' ? 'Yes' : 'No'}</TableCell>
                    {(canEdit || canDelete) && (
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          {canEdit && (
                            <Button variant="ghost" size="icon" onClick={() => openEdit(item)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                          )}
                          {canDelete && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-destructive hover:text-destructive"
                              disabled={isProtected}
                              onClick={() => setDeleteItem(item)}
                              title={isProtected ? 'Protected column cannot be deleted' : 'Delete column'}
                            >
                              {isProtected ? <Lock className="h-4 w-4" /> : <Trash2 className="h-4 w-4" />}
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </ScrollArea>
      )}

      {/* Add / Edit Column Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(o) => !o && closeDialog()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingItem ? 'Edit Column' : 'Add Column'}</DialogTitle>
            <DialogDescription>
              {editingItem ? 'Update column definition.' : 'Add a new column definition for team table and email cards.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit((d) => saveMutation.mutate(d))} className="space-y-4">
            <div className="space-y-1">
              <Label>Column Key *</Label>
              <Input
                {...register('column_key')}
                placeholder="e.g. department"
                disabled={!!editingItem && String(editingItem.is_protected).toLowerCase() === 'true'}
              />
              {errors.column_key && (
                <p className="text-xs text-destructive">{errors.column_key.message}</p>
              )}
            </div>
            <div className="space-y-1">
              <Label>Display Label *</Label>
              <Input {...register('column_label')} placeholder="e.g. Department" />
              {errors.column_label && (
                <p className="text-xs text-destructive">{errors.column_label.message}</p>
              )}
            </div>
            <div className={watchType === 'button' ? 'space-y-1' : 'grid grid-cols-2 gap-4'}>
              <div className="space-y-1">
                <Label>Type *</Label>
                <Controller
                  name="column_type"
                  control={control}
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="text">Text</SelectItem>
                        <SelectItem value="dropdown">Dropdown</SelectItem>
                        <SelectItem value="yes_no">Yes / No</SelectItem>
                        <SelectItem value="button">Button (hyperlink)</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              {watchType !== 'button' && (
                <div className="space-y-1">
                  <Label>Category *</Label>
                  <Controller
                    name="column_category"
                    control={control}
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="display">Display (read-only)</SelectItem>
                          <SelectItem value="input">Input (editable)</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
              )}
            </div>
            {watchType === 'dropdown' && (
              <div className="space-y-1">
                <Label>Dropdown Options (JSON array)</Label>
                <Input
                  {...register('dropdown_options')}
                  placeholder='["Option A", "Option B", "Option C"]'
                />
                <p className="text-xs text-muted-foreground">Enter a JSON array of strings.</p>
              </div>
            )}
            {watchType === 'button' && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Button behavior *</Label>
                  <div className="grid grid-cols-2 gap-1 rounded-md bg-muted p-1">
                    <button
                      type="button"
                      onClick={() => setButtonMode('builtin')}
                      className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                        buttonMode === 'builtin'
                          ? 'bg-background text-foreground shadow-sm'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Built-in upload page
                    </button>
                    <button
                      type="button"
                      onClick={() => setButtonMode('custom')}
                      className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                        buttonMode === 'custom'
                          ? 'bg-background text-foreground shadow-sm'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Custom URL
                    </button>
                  </div>
                </div>

                {buttonMode === 'builtin' ? (
                  <div className="rounded-md border border-primary/30 bg-primary/5 p-3 space-y-2 text-xs">
                    <div className="font-semibold text-foreground">
                      Each recipient sees a button labeled “{watch('column_label') || 'your label'}” in their email.
                    </div>
                    <div className="text-muted-foreground leading-relaxed">When they click it:</div>
                    <ol className="list-decimal pl-5 space-y-1 text-muted-foreground leading-relaxed">
                      <li>A secure upload page opens. The link is unique to that recipient + RFP and expires in <strong>72 hours</strong>.</li>
                      <li>They pick a <strong>TIR file</strong> and a <strong>Pricing file</strong> (max 25 MB each).</li>
                      <li>Files are saved to SharePoint at:<br/>
                        <code className="text-[10px] break-all">RFP-logs/ALLRFPs/&#123;Company&#125;/&#123;RFP&#125;/TDS-files/</code>
                      </li>
                      <li>The upload is recorded in Dataverse on that recipient&#39;s RFP response row.</li>
                    </ol>
                    <div className="pt-1">
                      <a
                        href="/upload?token=DEMO_PREVIEW"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-primary hover:underline"
                      >
                        ↗ Preview the upload page
                      </a>
                      <span className="text-muted-foreground"> (opens the real page with a fake token)</span>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <Label>Button URL *</Label>
                    <Input
                      {...register('button_url')}
                      placeholder="https://my-portal.example.com/{rfp_id}/upload"
                    />
                    <div className="rounded-md border border-border bg-muted/40 p-3 space-y-2 text-xs">
                      <div className="font-semibold text-foreground">Per-row placeholders</div>
                      <div className="text-muted-foreground leading-relaxed">
                        Replaced when the email is sent — values come from the recipient&#39;s row in the team table:
                      </div>
                      <ul className="space-y-0.5 font-mono text-[11px]">
                        <li><code>&#123;rfp_id&#125;</code><span className="text-muted-foreground"> → e.g. SEC RFP-c0047665</span></li>
                        <li><code>&#123;company_name&#125;</code><span className="text-muted-foreground"> → e.g. Saudi Energy</span></li>
                        <li><code>&#123;product&#125;</code><span className="text-muted-foreground"> → e.g. Cables</span></li>
                        <li><code>&#123;name&#125;</code><span className="text-muted-foreground"> → e.g. John Doe</span></li>
                        <li><code>&#123;email&#125;</code><span className="text-muted-foreground"> → e.g. john@bahra.com</span></li>
                      </ul>
                      <p className="text-muted-foreground leading-relaxed pt-1">
                        Note: this app does not handle the upload itself — whatever server you point at must accept the file.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
            <div className="space-y-1">
              <Label>Sort Order</Label>
              <Input {...register('sort_order')} placeholder="e.g. 6" type="number" />
            </div>
            <div className="flex items-center gap-6">
              <Controller
                name="is_required"
                control={control}
                render={({ field }) => (
                  <label className="flex items-center gap-2 cursor-pointer">
                    <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                    <span className="text-sm">Required</span>
                  </label>
                )}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={closeDialog}>Cancel</Button>
              <Button type="submit" loading={saveMutation.isPending}>
                {editingItem ? 'Save Changes' : 'Add Column'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Column Confirmation */}
      <AlertDialog open={!!deleteItem} onOpenChange={(o) => !o && setDeleteItem(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Column</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete column{' '}
              <span className="font-mono font-semibold">{deleteItem?.column_key}</span> ({deleteItem?.column_label})?
              This cannot be undone and will affect all email cards and response forms.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteItem && deleteMutation.mutate(deleteItem.record_id)}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Email Preview Dialog */}
      <Dialog open={previewOpen} onOpenChange={(o) => !o && setPreviewOpen(false)}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col p-0">
          <DialogHeader className="px-6 pt-6 pb-3 border-b">
            <DialogTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5" />
              Email Preview — Outlook
            </DialogTitle>
            <DialogDescription>
              Preview how the RFP notification email table will appear in Outlook.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-auto px-6 pb-6">
            {teamLoading ? (
              <div className="space-y-3 py-8">
                <Skeleton className="h-6 w-48" />
                <Skeleton className="h-40 w-full" />
              </div>
            ) : (
              <EmailPreviewContent columns={columns} teamMembers={teamData?.rfp_team ?? []} />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ─── Email Preview Component ─────────────────────────────────────────────────

function EmailPreviewContent({
  columns,
  teamMembers,
}: {
  columns: any[]
  teamMembers: any[]
}) {
  // Render an Outlook Adaptive Card-style input widget based on column type
  const renderInputWidget = (col: any) => {
    const widgetStyle: React.CSSProperties = {
      width: '100%',
      padding: '4px 8px',
      fontSize: 12,
      border: '1px solid #bbb',
      borderRadius: 3,
      backgroundColor: '#fff',
      color: '#333',
      fontFamily: 'Segoe UI, Calibri, Arial, sans-serif',
    }

    if (col.column_type === 'dropdown') {
      let options: string[] = []
      try {
        options = JSON.parse(col.dropdown_options || '[]')
      } catch { /* ignore */ }
      return (
        <select style={{ ...widgetStyle, cursor: 'pointer' }}>
          <option value="">{`Select ${col.column_label}...`}</option>
          {options.map((opt: string) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      )
    }

    if (col.column_type === 'yes_no') {
      return (
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
          <input
            type="checkbox"
            style={{ width: 16, height: 16, accentColor: '#0078d4', cursor: 'pointer' }}
          />
          <span>{col.column_label}</span>
        </label>
      )
    }

    // Default: text input
    return (
      <input
        type="text"
        placeholder={`Enter ${(col.column_label || '').toLowerCase()}...`}
        style={widgetStyle}
      />
    )
  }

  // Use sample data if no team members exist
  const members = teamMembers.length > 0
    ? teamMembers
    : [
        { product: 'Cables', name: 'John Doe', email: 'john@example.com' },
        { product: 'Transformers', name: 'Jane Smith', email: 'jane@example.com' },
      ]

  return (
    <div className="mt-4">
      {/* Outlook-like email shell */}
      <div
        style={{
          border: '1px solid #d0d0d0',
          borderRadius: 6,
          overflow: 'hidden',
          backgroundColor: '#ffffff',
          fontFamily: 'Segoe UI, Calibri, Arial, sans-serif',
        }}
      >
        {/* Email header bar */}
        <div
          style={{
            backgroundColor: '#0078d4',
            color: '#fff',
            padding: '10px 16px',
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: 0.3,
          }}
        >
          Outlook — Message Preview
        </div>

        {/* Email metadata */}
        <div
          style={{
            padding: '12px 20px',
            borderBottom: '1px solid #e8e8e8',
            fontSize: 13,
            color: '#333',
            lineHeight: 1.8,
          }}
        >
          <div><strong>From:</strong> Automation System &lt;automation@bahra-cables.com&gt;</div>
          <div><strong>To:</strong> RFP Team Members</div>
          <div><strong>Subject:</strong> <span style={{ fontWeight: 600 }}>New RFP — Sample RFP Title</span></div>
        </div>

        {/* Email body */}
        <div
          style={{
            padding: '20px 24px',
            fontSize: 14,
            color: '#1a1a1a',
            lineHeight: 1.6,
          }}
        >
          <p style={{ margin: '0 0 12px' }}>Dear's,</p>
          <p style={{ margin: '0 0 16px' }}>Kindly advise us regarding to the attached file</p>

          {/* Dynamic HTML table — matches _build_dynamic_html_table output */}
          <table
            style={{
              borderCollapse: 'collapse',
              margin: '10px 0',
              width: '100%',
              fontSize: 13,
            }}
          >
            <thead>
              <tr style={{ backgroundColor: '#f0f0f0' }}>
                {columns.map((col: any) => (
                  <th
                    key={col.column_key}
                    style={{
                      border: '1px solid #ccc',
                      padding: '6px 10px',
                      textAlign: 'left',
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {col.column_label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {members.map((member: any, idx: number) => {
                const isHighlighted = idx === 0
                return (
                  <tr
                    key={idx}
                    style={isHighlighted ? { backgroundColor: '#e8f4fd' } : undefined}
                  >
                    {columns.map((col: any) => {
                      const isInput = col.column_category === 'input'
                      const isButton = col.column_type === 'button'
                      const value = member[col.column_key] ?? ''

                      let cellContent: React.ReactNode = value

                      if (isButton) {
                        // Render a clickable hyperlink button. URL stored in dropdown_options;
                        // placeholders are substituted with sample values for preview.
                        const rawUrl = (col.dropdown_options || '').toString()
                        const sampleUrl = rawUrl
                          .replace(/\{upload_url\}/g, 'http://localhost:8000/upload?token=DEMO_PREVIEW')
                          .replace(/\{rfp_id\}/g, 'Sample-RFP-Title')
                          .replace(/\{company_name\}/g, 'Saudi Energy')
                          .replace(/\{product\}/g, encodeURIComponent(member.product || ''))
                          .replace(/\{name\}/g, encodeURIComponent(member.name || ''))
                          .replace(/\{email\}/g, encodeURIComponent(member.email || ''))
                        cellContent = (
                          <a
                            href={sampleUrl || '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              display: 'inline-block',
                              padding: '4px 12px',
                              backgroundColor: '#0078d4',
                              color: '#fff',
                              borderRadius: 3,
                              textDecoration: 'none',
                              fontSize: 12,
                              fontWeight: 600,
                            }}
                          >
                            {col.column_label}
                          </a>
                        )
                      } else if (isInput && isHighlighted) {
                        // Show actual widget for the highlighted (current) member
                        cellContent = renderInputWidget(col)
                      } else if (isInput) {
                        // Other members: show "Pending" like Adaptive Card
                        cellContent = (
                          <span style={{ color: '#b8860b', fontStyle: 'italic', fontSize: 12 }}>
                            Pending
                          </span>
                        )
                      } else if (col.column_key === 'name' && isHighlighted) {
                        cellContent = <strong>{value} (You)</strong>
                      }

                      return (
                        <td
                          key={col.column_key}
                          style={{
                            border: '1px solid #ccc',
                            padding: '6px 10px',
                            verticalAlign: 'middle',
                          }}
                        >
                          {cellContent}
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>

          {/* Due date highlight */}
          <p
            style={{
              backgroundColor: '#FFFF00',
              display: 'inline-block',
              padding: '4px 8px',
              margin: '8px 0',
              fontWeight: 600,
            }}
          >
            Note: the due date for <u>Sample RFP Title</u> is 3/15/2026
          </p>

          <br />
          <p style={{ margin: '16px 0 0' }}>
            Best Regards,<br />
            Automation System
          </p>
        </div>
      </div>

      <p className="text-xs text-muted-foreground mt-3">
        * The first row (highlighted) shows the Adaptive Card view for that team member — with actual input widgets. Other rows show "Pending" until they respond.
      </p>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MasterDataPage() {
  const canViewMaterials = useHasPermission('material_master.view')
  const canViewKeywords = useHasPermission('keyword_master.view')
  const canViewRfpTeam = useHasPermission('rfp_team.view')
  const canViewColumns = useHasPermission('column_config.view')

  // Default to the first visible tab
  const defaultTab = canViewMaterials ? 'materials'
    : canViewKeywords ? 'keywords'
    : canViewRfpTeam ? 'rfp-team'
    : canViewColumns ? 'column-config'
    : 'materials'

  return (
    <PageWrapper
      title="Master Data"
      description="Manage material master codes, keywords, RFP team assignments, and column definitions."
    >
      <Card>
        <CardContent className="p-6">
          <Tabs defaultValue={defaultTab}>
            <TabsList className="mb-6">
              {canViewMaterials && <TabsTrigger value="materials">Material Codes</TabsTrigger>}
              {canViewKeywords && <TabsTrigger value="keywords">Keywords</TabsTrigger>}
              {canViewRfpTeam && <TabsTrigger value="rfp-team">RFP Team</TabsTrigger>}
              {canViewColumns && <TabsTrigger value="column-config">Column Config</TabsTrigger>}
            </TabsList>
            {canViewMaterials && (
              <TabsContent value="materials">
                <MaterialsTab />
              </TabsContent>
            )}
            {canViewKeywords && (
              <TabsContent value="keywords">
                <KeywordsTab />
              </TabsContent>
            )}
            {canViewRfpTeam && (
              <TabsContent value="rfp-team">
                <RfpTeamTab />
              </TabsContent>
            )}
            {canViewColumns && (
              <TabsContent value="column-config">
                <ColumnConfigTab />
              </TabsContent>
            )}
          </Tabs>
        </CardContent>
      </Card>
    </PageWrapper>
  )
}
