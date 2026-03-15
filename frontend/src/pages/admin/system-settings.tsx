import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Eye,
  EyeOff,
  Pencil,
  RefreshCw,
  Search,
  Lock,
  Shield,
  Settings,
  Mail,
  Code2,
  KeyRound,
  Zap,
  HardDrive,
  FolderOpen,
  Database,
} from 'lucide-react'
import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent } from '@/components/ui/card'
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
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip'
import { useHasPermission } from '@/hooks/use-auth'
import { api } from '@/lib/api'
import { getSettingContext, IMPACT_CONFIG } from '@/lib/setting-context'

interface SystemSetting {
  key: string
  value: string
  label: string
  section: string
  sub_section: string
  data_type: string
  description: string
  is_editable: boolean
  is_sensitive: boolean
  id: string
}

// Two top-level sections, each with sub-tabs
const SECTION_CONFIG = [
  {
    id: 'Admin',
    label: 'Admin Settings',
    icon: Settings,
    subTabs: [
      { id: 'General', label: 'General', icon: Settings },
      { id: 'Email', label: 'Email', icon: Mail },
      { id: 'Security & Access', label: 'Security & Access', icon: Shield },
    ],
  },
  {
    id: 'Developer',
    label: 'Developer Settings',
    icon: Code2,
    subTabs: [
      { id: 'Azure & Auth', label: 'Azure & Auth', icon: KeyRound },
      { id: 'Automation', label: 'Automation', icon: Zap },
      { id: 'SharePoint', label: 'SharePoint', icon: HardDrive },
      { id: 'File Paths', label: 'File Paths', icon: FolderOpen },
      { id: 'Dataverse Tables', label: 'Dataverse Tables', icon: Database },
    ],
  },
] as const

function SystemSettingsPage() {
  const queryClient = useQueryClient()
  const canEdit = useHasPermission('system_settings.edit')

  // State
  const [search, setSearch] = useState('')
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set())
  const [revealedValues, setRevealedValues] = useState<Record<string, string>>({})
  const [activeSection, setActiveSection] = useState('Admin')
  const [activeSubTab, setActiveSubTab] = useState<Record<string, string>>({
    Admin: 'General',
    Developer: 'Azure & Auth',
  })

  // Edit dialog state
  const [editOpen, setEditOpen] = useState(false)
  const [editSetting, setEditSetting] = useState<SystemSetting | null>(null)
  const [editValue, setEditValue] = useState('')
  const [editError, setEditError] = useState('')

  // Queries
  const { data, isLoading } = useQuery({
    queryKey: ['system-settings'],
    queryFn: api.getSystemSettings,
  })

  const settings: SystemSetting[] = data?.settings || []

  // Mutations
  const updateMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      api.updateSetting(key, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-settings'] })
      toast.success('Setting updated successfully')
      setEditOpen(false)
      setEditSetting(null)
      if (editSetting) {
        setRevealedKeys((prev) => {
          const next = new Set(prev)
          next.delete(editSetting.key)
          return next
        })
      }
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to update setting')
    },
  })

  const reloadMutation = useMutation({
    mutationFn: api.reloadSettingsCache,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-settings'] })
      toast.success('Settings cache reloaded')
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to reload cache')
    },
  })

  // Filter settings by search
  const filteredSettings = settings.filter((s) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      s.label.toLowerCase().includes(q) ||
      s.key.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q)
    )
  })

  // Group settings by section → sub_section
  const settingsMap: Record<string, Record<string, SystemSetting[]>> = {}
  for (const s of filteredSettings) {
    const section = s.section || 'Admin'
    const sub = s.sub_section || 'General'
    if (!settingsMap[section]) settingsMap[section] = {}
    if (!settingsMap[section][sub]) settingsMap[section][sub] = []
    settingsMap[section][sub].push(s)
  }

  // Count settings per section (for badge)
  const sectionCounts: Record<string, number> = {}
  for (const [section, subs] of Object.entries(settingsMap)) {
    sectionCounts[section] = Object.values(subs).reduce((sum, arr) => sum + arr.length, 0)
  }

  // Reveal sensitive value
  const handleReveal = async (key: string) => {
    if (revealedKeys.has(key)) {
      setRevealedKeys((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
      return
    }
    try {
      const result = await api.revealSetting(key)
      setRevealedValues((prev) => ({ ...prev, [key]: result.value }))
      setRevealedKeys((prev) => new Set(prev).add(key))
    } catch (error: any) {
      toast.error(error.message || 'Failed to reveal value')
    }
  }

  // Open edit dialog
  const handleEdit = async (setting: SystemSetting) => {
    if (setting.is_sensitive) {
      try {
        const result = await api.revealSetting(setting.key)
        setEditValue(result.value)
      } catch (error: any) {
        toast.error(error.message || 'Failed to load value')
        return
      }
    } else {
      setEditValue(setting.value)
    }
    setEditSetting(setting)
    setEditError('')
    setEditOpen(true)
  }

  // Submit edit
  const handleSave = () => {
    if (!editSetting) return
    if (editSetting.data_type === 'json') {
      try {
        JSON.parse(editValue)
      } catch {
        setEditError('Invalid JSON format')
        return
      }
    }
    if (editSetting.data_type === 'number') {
      if (isNaN(Number(editValue))) {
        setEditError('Must be a valid number')
        return
      }
    }
    setEditError('')
    updateMutation.mutate({ key: editSetting.key, value: editValue })
  }

  // Render value display
  const renderValue = (setting: SystemSetting) => {
    if (setting.is_sensitive) {
      const isRevealed = revealedKeys.has(setting.key)
      const displayValue = isRevealed
        ? revealedValues[setting.key] || setting.value
        : setting.value
      return (
        <div className="flex items-center gap-2">
          <span
            className={`text-sm ${isRevealed ? 'font-mono text-slate-700' : 'text-slate-400'}`}
            style={{ maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'inline-block' }}
            title={isRevealed ? displayValue : undefined}
          >
            {displayValue}
          </span>
          {canEdit && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 shrink-0"
              onClick={() => handleReveal(setting.key)}
              title={isRevealed ? 'Hide value' : 'Reveal value'}
            >
              {isRevealed ? (
                <EyeOff className="h-3.5 w-3.5 text-slate-400" />
              ) : (
                <Eye className="h-3.5 w-3.5 text-slate-400" />
              )}
            </Button>
          )}
        </div>
      )
    }

    if (setting.data_type === 'json') {
      let displayVal = setting.value
      try {
        const parsed = JSON.parse(setting.value)
        if (Array.isArray(parsed)) {
          displayVal = `[${parsed.length} items]`
        } else if (typeof parsed === 'object') {
          displayVal = `{${Object.keys(parsed).length} keys}`
        }
      } catch {
        // Show raw
      }
      return (
        <span
          className="text-sm font-mono text-slate-600 cursor-pointer hover:text-slate-900"
          title={setting.value}
          style={{ maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'inline-block' }}
        >
          {displayVal}
        </span>
      )
    }

    return (
      <span
        className="text-sm text-slate-700"
        title={setting.value}
        style={{ maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'inline-block' }}
      >
        {setting.data_type === 'boolean'
          ? setting.value.toLowerCase() === 'true'
            ? 'Yes'
            : 'No'
          : setting.value}
      </span>
    )
  }

  const typeBadgeVariant = (type: string) => {
    switch (type) {
      case 'string': return 'secondary'
      case 'number': return 'default'
      case 'boolean': return 'outline'
      case 'json': return 'destructive'
      case 'email': return 'secondary'
      default: return 'secondary'
    }
  }

  // Render a single setting row
  const renderSettingRow = (setting: SystemSetting) => {
    const ctx = getSettingContext(setting.key)
    const impactCfg = ctx ? IMPACT_CONFIG[ctx.impact] : null

    return (
      <div
        key={setting.key}
        className="flex items-center gap-4 px-4 py-3 border-b last:border-b-0 hover:bg-slate-50/50 transition-colors"
      >
        <div className="w-[28%] min-w-0">
          <div className="flex items-center gap-1.5">
            {impactCfg && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className={`inline-block h-2 w-2 rounded-full shrink-0 ${impactCfg.bgColor}`} />
                </TooltipTrigger>
                <TooltipContent side="top" className="text-xs">
                  {impactCfg.label} impact
                </TooltipContent>
              </Tooltip>
            )}
            <span className="text-sm font-medium text-slate-800 truncate">
              {setting.label}
            </span>
          </div>
          {setting.description && (
            <Tooltip>
              <TooltipTrigger asChild>
                <p className="text-xs text-slate-400 mt-0.5 line-clamp-1 cursor-help">
                  {setting.description}
                </p>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-sm text-xs whitespace-normal">
                {setting.description}
              </TooltipContent>
            </Tooltip>
          )}
          {ctx && ctx.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {ctx.tags.map((tag) => (
                <span key={tag} className="text-[10px] px-1.5 py-0 rounded bg-slate-100 text-slate-500">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="w-[17%] min-w-0">
          <code className="text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded truncate block">
            {setting.key}
          </code>
        </div>
        <div className="w-[33%] min-w-0">
          {renderValue(setting)}
        </div>
        <div className="w-[8%]">
          <Badge variant={typeBadgeVariant(setting.data_type) as any} className="text-xs">
            {setting.data_type}
          </Badge>
        </div>
        <div className="w-[14%] text-right">
          {(() => {
            const isCritical = ctx?.impact === 'critical'
            if (setting.is_editable && canEdit && !isCritical) {
              return (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleEdit(setting)}
                  className="h-7 px-2"
                >
                  <Pencil className="h-3.5 w-3.5 mr-1" />
                  Edit
                </Button>
              )
            }
            return (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex items-center text-xs text-slate-400 cursor-help">
                    <Lock className="h-3 w-3 mr-1" />
                    {isCritical ? 'Protected' : 'Locked'}
                  </span>
                </TooltipTrigger>
                <TooltipContent side="left" className="text-xs max-w-xs">
                  {isCritical
                    ? 'Critical setting — change via Dataverse or seed script.'
                    : 'This setting is locked and cannot be edited from the UI.'}
                </TooltipContent>
              </Tooltip>
            )
          })()}
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <PageWrapper title="System Settings" description="Manage system configuration">
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-6 w-48 mb-4" />
                <div className="space-y-3">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </PageWrapper>
    )
  }

  return (
    <TooltipProvider delayDuration={300}>
    <PageWrapper
      title="System Settings"
      description="View and manage system configuration. Changes take effect immediately."
      actions={
        canEdit ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => reloadMutation.mutate()}
            disabled={reloadMutation.isPending}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${reloadMutation.isPending ? 'animate-spin' : ''}`} />
            Reload Cache
          </Button>
        ) : undefined
      }
    >
      {/* Search */}
      <div className="mb-6">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search settings by label, key, or description..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Top-level section toggle */}
      <div className="flex gap-2 mb-4">
        {SECTION_CONFIG.map((section) => {
          const Icon = section.icon
          const count = sectionCounts[section.id] || 0
          const isActive = activeSection === section.id
          return (
            <button
              key={section.id}
              onClick={() => setActiveSection(section.id)}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
                isActive
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              <Icon className="h-4 w-4" />
              {section.label}
              {count > 0 && (
                <Badge
                  variant={isActive ? 'outline' : 'secondary'}
                  className={`text-xs px-1.5 py-0 ${isActive ? 'border-slate-500 text-slate-300' : ''}`}
                >
                  {count}
                </Badge>
              )}
            </button>
          )
        })}
      </div>

      {/* Sub-tabs + content */}
      {SECTION_CONFIG.map((section) => {
        if (activeSection !== section.id) return null
        const currentSubTab = activeSubTab[section.id] || section.subTabs[0].id

        return (
          <div key={section.id}>
            <Tabs
              value={currentSubTab}
              onValueChange={(val) =>
                setActiveSubTab((prev) => ({ ...prev, [section.id]: val }))
              }
            >
              <TabsList className="mb-4">
                {section.subTabs.map((sub) => {
                  const SubIcon = sub.icon
                  const subSettings = settingsMap[section.id]?.[sub.id] || []
                  return (
                    <TabsTrigger key={sub.id} value={sub.id} className="gap-2">
                      <SubIcon className="h-3.5 w-3.5" />
                      {sub.label}
                      {subSettings.length > 0 && (
                        <Badge variant="secondary" className="text-xs ml-1 px-1.5 py-0">
                          {subSettings.length}
                        </Badge>
                      )}
                    </TabsTrigger>
                  )
                })}
              </TabsList>

              {section.subTabs.map((sub) => {
                const subSettings = settingsMap[section.id]?.[sub.id] || []
                return (
                  <TabsContent key={sub.id} value={sub.id}>
                    <Card>
                      {/* Column headers */}
                      <div className="flex items-center gap-4 px-4 py-2 border-b bg-slate-50/50">
                        <div className="w-[28%] text-xs font-medium text-slate-500">Setting</div>
                        <div className="w-[17%] text-xs font-medium text-slate-500">Key</div>
                        <div className="w-[33%] text-xs font-medium text-slate-500">Value</div>
                        <div className="w-[8%] text-xs font-medium text-slate-500">Type</div>
                        <div className="w-[14%] text-xs font-medium text-slate-500 text-right">Action</div>
                      </div>
                      <CardContent className="p-0">
                        {subSettings.length > 0 ? (
                          subSettings.map((s) => renderSettingRow(s))
                        ) : (
                          <div className="text-center py-8 text-slate-400 text-sm">
                            No settings found{search ? ' matching your search' : ''}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </TabsContent>
                )
              })}
            </Tabs>
          </div>
        )
      })}

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Edit Setting</DialogTitle>
            <DialogDescription>
              {editSetting?.label}
              {editSetting?.description && (
                <span className="block mt-1 text-xs">{editSetting.description}</span>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label className="text-xs text-slate-500">Key</Label>
              <code className="block text-sm bg-slate-100 px-3 py-2 rounded">
                {editSetting?.key}
              </code>
            </div>

            {/* Context panel */}
            {editSetting && (() => {
              const ctx = getSettingContext(editSetting.key)
              if (!ctx) return null
              const cfg = IMPACT_CONFIG[ctx.impact]
              return (
                <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2.5 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className={`inline-block h-2.5 w-2.5 rounded-full ${cfg.bgColor}`} />
                    <span className={`text-xs font-semibold ${cfg.color}`}>{cfg.label} Impact</span>
                  </div>
                  {ctx.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {ctx.tags.map((tag) => (
                        <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-500">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  {ctx.relatedKeys && ctx.relatedKeys.length > 0 && (
                    <p className="text-[11px] text-slate-500">
                      Related: {ctx.relatedKeys.map((k) => (
                        <code key={k} className="text-[10px] bg-white border border-slate-200 px-1 py-0.5 rounded mx-0.5">{k}</code>
                      ))}
                    </p>
                  )}
                </div>
              )
            })()}

            <div className="space-y-2">
              <Label htmlFor="edit-value">Value</Label>

              {editSetting?.data_type === 'boolean' ? (
                <div className="flex items-center gap-3 py-2">
                  <Checkbox
                    id="edit-value"
                    checked={editValue.toLowerCase() === 'true'}
                    onCheckedChange={(checked) =>
                      setEditValue(checked ? 'true' : 'false')
                    }
                  />
                  <Label htmlFor="edit-value" className="text-sm cursor-pointer">
                    {editValue.toLowerCase() === 'true' ? 'Enabled (true)' : 'Disabled (false)'}
                  </Label>
                </div>
              ) : editSetting?.data_type === 'json' ? (
                <textarea
                  id="edit-value"
                  value={editValue}
                  onChange={(e) => {
                    setEditValue(e.target.value)
                    setEditError('')
                  }}
                  rows={8}
                  className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-mono shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
                  placeholder="Enter valid JSON..."
                />
              ) : editSetting?.data_type === 'number' ? (
                <Input
                  id="edit-value"
                  type="number"
                  value={editValue}
                  onChange={(e) => {
                    setEditValue(e.target.value)
                    setEditError('')
                  }}
                />
              ) : (
                <Input
                  id="edit-value"
                  type={editSetting?.data_type === 'email' ? 'email' : 'text'}
                  value={editValue}
                  onChange={(e) => {
                    setEditValue(e.target.value)
                    setEditError('')
                  }}
                />
              )}

              {editError && (
                <p className="text-xs text-red-500 mt-1">{editError}</p>
              )}

              {editSetting?.is_sensitive && (
                <p className="text-xs text-amber-600 flex items-center gap-1 mt-1">
                  <Eye className="h-3 w-3" />
                  This is a sensitive value. Changes will be logged.
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageWrapper>
    </TooltipProvider>
  )
}

export default SystemSettingsPage
