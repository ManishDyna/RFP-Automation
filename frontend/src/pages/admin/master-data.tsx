import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Database, Pencil, Plus, Search, Trash2, Upload } from 'lucide-react'

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

const rfpTeamSchema = z.object({
  product: z.string().min(1, 'Product is required').max(200),
  name: z.string().min(1, 'Name is required').max(200),
  email: z.string().min(1, 'Email is required').email('Must be a valid email').max(300),
})
type RfpTeamForm = z.infer<typeof rfpTeamSchema>

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
  const canCreate = useHasPermission('master_data.create')
  const canEdit   = useHasPermission('master_data.edit')
  const canDelete = useHasPermission('master_data.delete')

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
  const canCreate = useHasPermission('master_data.create')
  const canEdit   = useHasPermission('master_data.edit')
  const canDelete = useHasPermission('master_data.delete')

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

// ─── RFP Team Tab ────────────────────────────────────────────────────────────

function RfpTeamTab() {
  const queryClient = useQueryClient()
  const canCreate = useHasPermission('master_data.create')
  const canEdit   = useHasPermission('master_data.edit')
  const canDelete = useHasPermission('master_data.delete')

  const [search, setSearch]           = useState('')
  const [dialogOpen, setDialogOpen]   = useState(false)
  const [editingItem, setEditingItem] = useState<any>(null)
  const [deleteItem, setDeleteItem]   = useState<any>(null)
  const [importOpen, setImportOpen]   = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['rfp-team', search],
    queryFn: () => api.getRfpTeam({ search: search || undefined, page_size: 500 }),
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RfpTeamForm>({ resolver: zodResolver(rfpTeamSchema) })

  const closeDialog = () => {
    setDialogOpen(false)
    setEditingItem(null)
    reset()
  }

  const openAdd = () => {
    setEditingItem(null)
    reset({ product: '', name: '', email: '' })
    setDialogOpen(true)
  }

  const openEdit = (item: any) => {
    setEditingItem(item)
    reset({ product: item.product ?? '', name: item.name ?? '', email: item.email ?? '' })
    setDialogOpen(true)
  }

  const saveMutation = useMutation({
    mutationFn: (formData: RfpTeamForm) =>
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

      {/* Table */}
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
                <TableHead className="w-[180px]">Product</TableHead>
                <TableHead className="w-[180px]">Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead className="w-[120px]">Created</TableHead>
                {(canEdit || canDelete) && <TableHead className="text-right w-[100px]">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((item: any) => (
                <TableRow key={item.record_id}>
                  <TableCell className="font-medium">{item.product}</TableCell>
                  <TableCell>{item.name}</TableCell>
                  <TableCell className="font-mono text-sm text-muted-foreground">{item.email}</TableCell>
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
            <DialogTitle>{editingItem ? 'Edit Team Member' : 'Add Team Member'}</DialogTitle>
            <DialogDescription>
              {editingItem ? 'Update the team member details.' : 'Add a new RFP team member for product-based email routing.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit((d) => saveMutation.mutate(d))} className="space-y-4">
            <div className="space-y-1">
              <Label>Product *</Label>
              <Input {...register('product')} placeholder="e.g. Cables" />
              {errors.product && (
                <p className="text-xs text-destructive">{errors.product.message}</p>
              )}
            </div>
            <div className="space-y-1">
              <Label>Name *</Label>
              <Input {...register('name')} placeholder="e.g. John Doe" />
              {errors.name && (
                <p className="text-xs text-destructive">{errors.name.message}</p>
              )}
            </div>
            <div className="space-y-1">
              <Label>Email *</Label>
              <Input {...register('email')} type="email" placeholder="e.g. john.doe@company.com" />
              {errors.email && (
                <p className="text-xs text-destructive">{errors.email.message}</p>
              )}
            </div>
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MasterDataPage() {
  return (
    <PageWrapper
      title="Master Data"
      description="Manage material master codes, keywords, and RFP team assignments."
    >
      <Card>
        <CardContent className="p-6">
          <Tabs defaultValue="materials">
            <TabsList className="mb-6">
              <TabsTrigger value="materials">Material Codes</TabsTrigger>
              <TabsTrigger value="keywords">Keywords</TabsTrigger>
              <TabsTrigger value="rfp-team">RFP Team</TabsTrigger>
            </TabsList>
            <TabsContent value="materials">
              <MaterialsTab />
            </TabsContent>
            <TabsContent value="keywords">
              <KeywordsTab />
            </TabsContent>
            <TabsContent value="rfp-team">
              <RfpTeamTab />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </PageWrapper>
  )
}
