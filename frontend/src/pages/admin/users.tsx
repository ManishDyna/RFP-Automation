import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import {
  Users,
  Plus,
  Pencil,
  Trash2,
  Search,
  ShieldCheck,
  ShieldOff,
  Unlock,
  Lock,
} from 'lucide-react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from '@/components/ui/tooltip'
import { api } from '@/lib/api'
import { useHasPermission } from '@/hooks/use-auth'

const userSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Please enter a valid email'),
  mobile: z.string().optional(),
  role: z.string().min(1, 'Please select a role'),
  password: z.string().min(6, 'Password must be at least 6 characters').optional(),
})

type UserFormData = z.infer<typeof userSchema>

export default function UserManagementPage() {
  const queryClient = useQueryClient()
  const canCreate = useHasPermission('user_management.create')
  const canEdit = useHasPermission('user_management.edit')
  const canDelete = useHasPermission('user_management.delete')
  const canActivate = useHasPermission('user_management.activate')
  const [searchTerm, setSearchTerm] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<any>(null)
  const [deleteUser, setDeleteUser] = useState<any>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: api.getUsers,
  })

  const { data: rolesData } = useQuery({
    queryKey: ['roles'],
    queryFn: api.getRoles,
  })

  const createMutation = useMutation({
    mutationFn: (userData: UserFormData) => api.createUser(userData as any),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('User created successfully')
      setDialogOpen(false)
      reset()
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to create user')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UserFormData }) =>
      api.updateUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('User updated successfully')
      setDialogOpen(false)
      setEditingUser(null)
      reset()
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to update user')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('User deleted successfully')
      setDeleteUser(null)
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to delete user')
    },
  })

  const activateMutation = useMutation({
    mutationFn: (id: string) => api.activateUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('User activated successfully')
    },
    onError: (error: any) => toast.error(error.message || 'Failed to activate user'),
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => api.deactivateUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('User deactivated successfully')
    },
    onError: (error: any) => toast.error(error.message || 'Failed to deactivate user'),
  })

  const unlockMutation = useMutation({
    mutationFn: (id: string) => api.unlockUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('User account unlocked')
    },
    onError: (error: any) => toast.error(error.message || 'Failed to unlock user'),
  })

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<UserFormData>({
    resolver: zodResolver(userSchema),
    defaultValues: {
      name: '',
      email: '',
      mobile: '',
      role: '',
      password: '',
    },
  })

  const users = data?.users || []
  const availableRoles = (rolesData?.roles || []).filter(
    (r: any) => String(r.is_active || 'true').toLowerCase() !== 'false'
  )
  const filteredUsers = searchTerm
    ? users.filter((user: any) =>
        user.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        user.email?.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : users

  const handleEdit = (user: any) => {
    setEditingUser(user)
    setValue('name', user.name || '')
    setValue('email', user.email || '')
    setValue('mobile', user.mobile_number || '')
    setValue('role', user.role || '')
    setValue('password', '')
    setDialogOpen(true)
  }

  const handleAdd = () => {
    setEditingUser(null)
    reset()
    setDialogOpen(true)
  }

  const onSubmit = (data: UserFormData) => {
    if (editingUser) {
      updateMutation.mutate({ id: editingUser.record_id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  return (
    <PageWrapper
      title="User Management"
      description="Manage system users and their permissions"
      actions={
        canCreate ? (
          <Button onClick={handleAdd}>
            <Plus className="h-4 w-4 mr-2" />
            Add User
          </Button>
        ) : undefined
      }
    >
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <Users className="h-5 w-5" />
            Users
          </CardTitle>
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search users..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Users className="h-12 w-12 mb-4 opacity-50" />
              <p>No users found</p>
            </div>
          ) : (
            <ScrollArea className="h-[500px]">
              <Table>
                <TableHeader className="sticky top-0 bg-background z-10">
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Mobile</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead className="text-center">Status</TableHead>
                    <TableHead>Created</TableHead>
                    {(canEdit || canDelete || canActivate) && (
                      <TableHead className="text-right">Actions</TableHead>
                    )}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.map((user: any) => {
                    const isActive = String(user.is_active || 'true').toLowerCase() !== 'false'
                    const isLocked = String(user.is_locked || '').toLowerCase() === 'true'
                    return (
                      <TableRow key={user.record_id}>
                        <TableCell className="font-medium">{user.name}</TableCell>
                        <TableCell>{user.email}</TableCell>
                        <TableCell>{user.mobile_number || '-'}</TableCell>
                        <TableCell>
                          <Badge
                            variant={user.role?.toLowerCase() === 'admin' ? 'default' : 'secondary'}
                          >
                            {user.role || 'User'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-center">
                          {isLocked ? (
                            <Badge variant="destructive" className="gap-1">
                              <Lock className="h-3 w-3" />
                              Locked
                            </Badge>
                          ) : isActive ? (
                            <Badge className="bg-green-100 text-green-700 hover:bg-green-100">Active</Badge>
                          ) : (
                            <Badge variant="secondary" className="bg-slate-100 text-slate-500">Inactive</Badge>
                          )}
                        </TableCell>
                        <TableCell>{user.created_display || '-'}</TableCell>
                        {(canEdit || canDelete || canActivate) && (
                          <TableCell className="text-right">
                            <TooltipProvider delayDuration={0}>
                              <div className="flex items-center justify-end gap-1">
                                {canEdit && (
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        size="icon"
                                        variant="ghost"
                                        className="h-8 w-8"
                                        onClick={() => handleEdit(user)}
                                      >
                                        <Pencil className="h-4 w-4" />
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>Edit user</TooltipContent>
                                  </Tooltip>
                                )}
                                {canActivate && isActive && !isLocked && (
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        size="icon"
                                        variant="ghost"
                                        className="h-8 w-8 text-orange-500 hover:text-orange-600"
                                        onClick={() => deactivateMutation.mutate(user.record_id)}
                                      >
                                        <ShieldOff className="h-4 w-4" />
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>Deactivate user</TooltipContent>
                                  </Tooltip>
                                )}
                                {canActivate && !isActive && (
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        size="icon"
                                        variant="ghost"
                                        className="h-8 w-8 text-green-600 hover:text-green-700"
                                        onClick={() => activateMutation.mutate(user.record_id)}
                                      >
                                        <ShieldCheck className="h-4 w-4" />
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>Activate user</TooltipContent>
                                  </Tooltip>
                                )}
                                {canEdit && isLocked && (
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        size="icon"
                                        variant="ghost"
                                        className="h-8 w-8 text-blue-600 hover:text-blue-700"
                                        onClick={() => unlockMutation.mutate(user.record_id)}
                                      >
                                        <Unlock className="h-4 w-4" />
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>Unlock account</TooltipContent>
                                  </Tooltip>
                                )}
                                {canDelete && (
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        size="icon"
                                        variant="ghost"
                                        className="h-8 w-8 text-destructive hover:text-destructive"
                                        onClick={() => setDeleteUser(user)}
                                      >
                                        <Trash2 className="h-4 w-4" />
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>Delete user</TooltipContent>
                                  </Tooltip>
                                )}
                              </div>
                            </TooltipProvider>
                          </TableCell>
                        )}
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit User Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingUser ? 'Edit User' : 'Add New User'}
            </DialogTitle>
            <DialogDescription>
              {editingUser
                ? 'Update user information below.'
                : 'Fill in the details to create a new user.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name *</Label>
              <Input
                id="name"
                {...register('name')}
                placeholder="Full name"
              />
              {errors.name && (
                <p className="text-sm text-destructive">{errors.name.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email *</Label>
              <Input
                id="email"
                type="email"
                {...register('email')}
                placeholder="user@company.com"
                disabled={!!editingUser}
              />
              {errors.email && (
                <p className="text-sm text-destructive">{errors.email.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="mobile">Mobile</Label>
              <Input
                id="mobile"
                {...register('mobile')}
                placeholder="+1 234 567 8900"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="role">Role *</Label>
              <Select
                value={watch('role')}
                onValueChange={(value) => setValue('role', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  {availableRoles.length > 0 ? (
                    availableRoles.map((role: any) => (
                      <SelectItem key={role.record_id} value={role.name}>
                        {role.name}
                      </SelectItem>
                    ))
                  ) : (
                    <>
                      <SelectItem value="Admin">Admin</SelectItem>
                      <SelectItem value="RFP Bidder">RFP Bidder</SelectItem>
                    </>
                  )}
                </SelectContent>
              </Select>
              {errors.role && (
                <p className="text-sm text-destructive">{errors.role.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">
                Password {editingUser ? '(leave blank to keep current)' : '*'}
              </Label>
              <Input
                id="password"
                type="password"
                {...register('password')}
                placeholder={editingUser ? '••••••••' : 'Enter password'}
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                loading={createMutation.isPending || updateMutation.isPending}
              >
                {editingUser ? 'Save Changes' : 'Create User'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteUser} onOpenChange={() => setDeleteUser(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete User</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {deleteUser?.name}? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteUser && deleteMutation.mutate(deleteUser.record_id)}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageWrapper>
  )
}
