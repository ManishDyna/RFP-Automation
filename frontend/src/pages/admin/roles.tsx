import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import {
  Shield,
  Plus,
  Pencil,
  Trash2,
  Search,
  ChevronDown,
  ChevronRight,
  ToggleLeft,
  ToggleRight,
  AlertTriangle,
} from 'lucide-react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { useHasPermission } from '@/hooks/use-auth'

const roleSchema = z.object({
  name: z.string().min(2, 'Role name must be at least 2 characters'),
  description: z.string().optional(),
})

type RoleFormData = z.infer<typeof roleSchema>

interface PermissionGroup {
  label: string
  permissions: Record<string, string>
}

export default function RoleManagementPage() {
  const queryClient = useQueryClient()
  const canCreate = useHasPermission('role_management.create')
  const canEdit = useHasPermission('role_management.edit')
  const canDelete = useHasPermission('role_management.delete')

  const [searchTerm, setSearchTerm] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingRole, setEditingRole] = useState<any>(null)
  const [hardDeleteRole, setHardDeleteRole] = useState<any>(null)
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([])
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})

  const { data: rolesData, isLoading } = useQuery({
    queryKey: ['roles'],
    queryFn: api.getRoles,
  })

  const { data: permissionsData } = useQuery({
    queryKey: ['permissions'],
    queryFn: api.getAllPermissions,
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RoleFormData>({
    resolver: zodResolver(roleSchema),
  })

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description: string; permissions: string[] }) =>
      api.createRole(data),
    onSuccess: () => {
      toast.success('Role created successfully')
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      closeDialog()
    },
    onError: (err: any) => toast.error(err.message || 'Failed to create role'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.updateRole(id, data),
    onSuccess: () => {
      toast.success('Role updated successfully')
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      closeDialog()
    },
    onError: (err: any) => toast.error(err.message || 'Failed to update role'),
  })

  const updatePermsMutation = useMutation({
    mutationFn: ({ id, permissions }: { id: string; permissions: string[] }) =>
      api.setRolePermissions(id, permissions),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
    },
  })

  const toggleStatusMutation = useMutation({
    mutationFn: (id: string) => api.toggleRoleStatus(id),
    onSuccess: (data: any) => {
      toast.success(data.message || 'Role status updated')
      queryClient.invalidateQueries({ queryKey: ['roles'] })
    },
    onError: (err: any) => toast.error(err.message || 'Failed to toggle role status'),
  })

  const hardDeleteMutation = useMutation({
    mutationFn: (id: string) => api.hardDeleteRole(id),
    onSuccess: () => {
      toast.success('Role permanently deleted')
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      setHardDeleteRole(null)
    },
    onError: (err: any) => toast.error(err.message || 'Failed to permanently delete role'),
  })

  function closeDialog() {
    setDialogOpen(false)
    setEditingRole(null)
    setSelectedPermissions([])
    reset({ name: '', description: '' })
  }

  function openCreateDialog() {
    setEditingRole(null)
    setSelectedPermissions([])
    reset({ name: '', description: '' })
    // Expand all groups by default
    if (permissionsData?.groups) {
      const expanded: Record<string, boolean> = {}
      Object.keys(permissionsData.groups).forEach((g) => (expanded[g] = true))
      setExpandedGroups(expanded)
    }
    setDialogOpen(true)
  }

  async function openEditDialog(role: any) {
    setEditingRole(role)
    reset({ name: role.name || '', description: role.description || '' })
    // Expand all groups
    if (permissionsData?.groups) {
      const expanded: Record<string, boolean> = {}
      Object.keys(permissionsData.groups).forEach((g) => (expanded[g] = true))
      setExpandedGroups(expanded)
    }
    // Fetch current permissions
    try {
      const res = await api.getRolePermissions(role.record_id)
      setSelectedPermissions(res.permissions || [])
    } catch {
      setSelectedPermissions([])
    }
    setDialogOpen(true)
  }

  function onSubmit(data: RoleFormData) {
    if (editingRole) {
      updateMutation.mutate(
        { id: editingRole.record_id, data: { name: data.name, description: data.description } },
        {
          onSuccess: () => {
            updatePermsMutation.mutate({ id: editingRole.record_id, permissions: selectedPermissions })
          },
        }
      )
    } else {
      createMutation.mutate({
        name: data.name,
        description: data.description || '',
        permissions: selectedPermissions,
      })
    }
  }

  function togglePermission(key: string) {
    setSelectedPermissions((prev) =>
      prev.includes(key) ? prev.filter((p) => p !== key) : [...prev, key]
    )
  }

  function toggleGroup(groupKey: string) {
    if (!permissionsData?.groups?.[groupKey]) return
    const groupPerms = Object.keys(permissionsData.groups[groupKey].permissions)
    const allSelected = groupPerms.every((p) => selectedPermissions.includes(p))
    if (allSelected) {
      setSelectedPermissions((prev) => prev.filter((p) => !groupPerms.includes(p)))
    } else {
      setSelectedPermissions((prev) => [...new Set([...prev, ...groupPerms])])
    }
  }

  const roles = (rolesData?.roles || []).filter((r: any) => {
    if (!searchTerm) return true
    const q = searchTerm.toLowerCase()
    return (
      (r.name || '').toLowerCase().includes(q) ||
      (r.description || '').toLowerCase().includes(q)
    )
  })

  const groups: Record<string, PermissionGroup> = permissionsData?.groups || {}

  return (
    <PageWrapper
      title="Role Management"
      description="Create and manage roles with granular permissions"
      actions={
        canCreate ? (
          <Button onClick={openCreateDialog} size="sm">
            <Plus className="h-4 w-4 mr-1" /> Create Role
          </Button>
        ) : undefined
      }
    >
      <Card>
        <CardContent className="p-6">
          {/* Search */}
          <div className="flex items-center gap-3 mb-6">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search roles..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : (
            <ScrollArea className="h-[calc(100vh-320px)]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Role Name</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-center">Permissions</TableHead>
                    <TableHead className="text-center">Type</TableHead>
                    <TableHead className="text-center">Status</TableHead>
                    {(canEdit || canDelete) && <TableHead className="text-right">Actions</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {roles.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-10 text-slate-400">
                        <Shield className="h-10 w-10 mx-auto mb-3 opacity-30" />
                        No roles found
                      </TableCell>
                    </TableRow>
                  ) : (
                    roles.map((role: any) => {
                      const isSystem =
                        String(role.is_system || '').toLowerCase() === 'true' ||
                        role.is_system === true
                      const isAdmin = (role.name || '').toLowerCase() === 'admin'
                      const isActive =
                        String(role.is_active || 'true').toLowerCase() !== 'false'
                      return (
                        <TableRow key={role.record_id}>
                          <TableCell className="font-medium">{role.name}</TableCell>
                          <TableCell className="text-slate-500 max-w-[300px] truncate">
                            {role.description || '-'}
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge variant="secondary">{role.permissions_count || 0}</Badge>
                          </TableCell>
                          <TableCell className="text-center">
                            {isSystem ? (
                              <Badge variant="outline" className="text-blue-600 border-blue-200 bg-blue-50">
                                System
                              </Badge>
                            ) : (
                              <Badge variant="outline">Custom</Badge>
                            )}
                          </TableCell>
                          <TableCell className="text-center">
                            {isActive ? (
                              <Badge className="bg-green-100 text-green-700 hover:bg-green-100">Active</Badge>
                            ) : (
                              <Badge variant="destructive">Inactive</Badge>
                            )}
                          </TableCell>
                          {(canEdit || canDelete) && (
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end gap-1">
                                {canEdit && (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => openEditDialog(role)}
                                    className="h-8 w-8"
                                    title="Edit role"
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </Button>
                                )}
                                {canEdit && !isAdmin && (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => toggleStatusMutation.mutate(role.record_id)}
                                    className={`h-8 w-8 ${isActive ? 'text-amber-500 hover:text-amber-600' : 'text-green-500 hover:text-green-600'}`}
                                    title={isActive ? 'Deactivate role' : 'Activate role'}
                                    disabled={toggleStatusMutation.isPending}
                                  >
                                    {isActive ? <ToggleRight className="h-4 w-4" /> : <ToggleLeft className="h-4 w-4" />}
                                  </Button>
                                )}
                                {canDelete && !isAdmin && (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => setHardDeleteRole(role)}
                                    className="h-8 w-8 text-red-500 hover:text-red-600"
                                    title="Permanently delete role"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </Button>
                                )}
                              </div>
                            </TableCell>
                          )}
                        </TableRow>
                      )
                    })
                  )}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(open) => !open && closeDialog()}>
        <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>{editingRole ? 'Edit Role' : 'Create Role'}</DialogTitle>
            <DialogDescription>
              {editingRole
                ? 'Update role details and permissions'
                : 'Create a new role and assign permissions'}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col flex-1 overflow-hidden">
            <div className="space-y-4 mb-4">
              <div>
                <Label htmlFor="name">Role Name</Label>
                <Input id="name" {...register('name')} placeholder="e.g. Manager" />
                {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name.message}</p>}
              </div>
              <div>
                <Label htmlFor="description">Description</Label>
                <Input
                  id="description"
                  {...register('description')}
                  placeholder="Brief description of this role"
                />
              </div>
            </div>

            {/* Permissions */}
            <div className="mb-2">
              <Label>
                Permissions ({selectedPermissions.length} selected)
              </Label>
            </div>
            <ScrollArea style={{ height: '100px', overflow: 'scroll' }}  className="h-0 flex-1 min-h-[200px] border rounded-md p-3" viewportClassName="!overflow-y-scroll">
              <div className="space-y-2">
                {Object.entries(groups).map(([groupKey, group]) => {
                  const groupPerms = Object.keys(group.permissions)
                  const selectedInGroup = groupPerms.filter((p) =>
                    selectedPermissions.includes(p)
                  ).length
                  const allSelected = selectedInGroup === groupPerms.length
                  const isExpanded = expandedGroups[groupKey]

                  return (
                    <div key={groupKey} className="border rounded-md">
                      <div
                        className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-slate-50"
                        onClick={() =>
                          setExpandedGroups((prev) => ({
                            ...prev,
                            [groupKey]: !prev[groupKey],
                          }))
                        }
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4 text-slate-400" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-slate-400" />
                        )}
                        <span className="font-medium text-sm flex-1">{group.label}</span>
                        <span className="text-xs text-slate-400">
                          {selectedInGroup}/{groupPerms.length}
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-xs"
                          onClick={(e) => {
                            e.stopPropagation()
                            toggleGroup(groupKey)
                          }}
                        >
                          {allSelected ? 'Deselect All' : 'Select All'}
                        </Button>
                      </div>
                      {isExpanded && (
                        <div className="px-3 pb-2 space-y-1 ml-6">
                          {Object.entries(group.permissions).map(([permKey, permLabel]) => (
                            <label
                              key={permKey}
                              className="flex items-center gap-2 py-1 cursor-pointer hover:bg-slate-50 rounded px-1"
                            >
                              <Checkbox
                                checked={selectedPermissions.includes(permKey)}
                                onCheckedChange={() => togglePermission(permKey)}
                              />
                              <span className="text-sm">{permLabel}</span>
                              <span className="text-xs text-slate-400 ml-auto font-mono">
                                {permKey}
                              </span>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </ScrollArea>

            <DialogFooter className="mt-4">
              <Button type="button" variant="outline" onClick={closeDialog}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {editingRole ? 'Update Role' : 'Create Role'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Hard Delete Confirmation */}
      <AlertDialog open={!!hardDeleteRole} onOpenChange={(open) => !open && setHardDeleteRole(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              Permanently Delete Role
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <span className="block">
                Are you sure you want to permanently delete the role <strong>"{hardDeleteRole?.name}"</strong>?
              </span>
              <span className="block text-red-600 font-medium">
                This action cannot be undone. The role and all its permission mappings will be permanently removed.
                Users with this role will lose all access.
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => hardDeleteRole && hardDeleteMutation.mutate(hardDeleteRole.record_id)}
              className="bg-red-600 hover:bg-red-700"
            >
              Delete Permanently
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageWrapper>
  )
}
