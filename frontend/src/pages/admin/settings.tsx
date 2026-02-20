import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Settings,
  Mail,
  Database,
  Globe,
  Zap,
  Users2,
  Eye,
  EyeOff,
  RefreshCw,
  Save,
  Plus,
  Trash2,
} from 'lucide-react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { api, SettingEntry } from '@/lib/api'

// ─── Types ───────────────────────────────────────────────────────────────────

interface RfpTeamRow {
  product: string
  name: string
}

interface SectionData {
  [key: string]: SettingEntry[]
}

// ─── Helper components ────────────────────────────────────────────────────────

function SensitiveInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <Input
        type={show ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="pr-10 font-mono text-sm"
      />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  )
}

function SettingField({
  entry,
  localValue,
  onChange,
}: {
  entry: SettingEntry
  localValue: string
  onChange: (key: string, value: string) => void
}) {
  if (entry.data_type === 'json_list') {
    // Render as textarea: one item per line, convert to/from JSON
    let lines = ''
    try {
      const arr = JSON.parse(localValue || '[]')
      lines = Array.isArray(arr) ? arr.join('\n') : localValue
    } catch {
      lines = localValue
    }
    return (
      <textarea
        value={lines}
        onChange={(e) => {
          const arr = e.target.value.split('\n').map((l) => l.trim()).filter(Boolean)
          onChange(entry.key, JSON.stringify(arr))
        }}
        rows={4}
        placeholder="One entry per line"
        className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 font-mono text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
      />
    )
  }

  if (entry.is_sensitive) {
    return (
      <SensitiveInput
        value={localValue}
        onChange={(v) => onChange(entry.key, v)}
        placeholder={entry.label}
      />
    )
  }

  return (
    <Input
      value={localValue}
      onChange={(e) => onChange(entry.key, e.target.value)}
      placeholder={entry.label}
      className="font-mono text-sm"
    />
  )
}

// ─── RFP Team Section ────────────────────────────────────────────────────────

function RfpTeamSection({
  entry,
  localValue,
  onChange,
}: {
  entry: SettingEntry
  localValue: string
  onChange: (key: string, value: string) => void
}) {
  const [rows, setRows] = useState<RfpTeamRow[]>(() => {
    try {
      return JSON.parse(localValue || '[]')
    } catch {
      return []
    }
  })

  useEffect(() => {
    onChange(entry.key, JSON.stringify(rows))
  }, [rows]) // eslint-disable-line react-hooks/exhaustive-deps

  const updateRow = (index: number, field: keyof RfpTeamRow, value: string) => {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)))
  }

  const addRow = () => setRows((prev) => [...prev, { product: '', name: '' }])

  const removeRow = (index: number) => setRows((prev) => prev.filter((_, i) => i !== index))

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              <th className="px-4 py-2 text-left font-medium text-slate-600">Product Category</th>
              <th className="px-4 py-2 text-left font-medium text-slate-600">Responsible Person</th>
              <th className="px-4 py-2 w-12"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2">
                  <Input
                    value={row.product}
                    onChange={(e) => updateRow(i, 'product', e.target.value)}
                    placeholder="e.g. Cables"
                    className="h-8 text-sm"
                  />
                </td>
                <td className="px-4 py-2">
                  <Input
                    value={row.name}
                    onChange={(e) => updateRow(i, 'name', e.target.value)}
                    placeholder="e.g. John Smith"
                    className="h-8 text-sm"
                  />
                </td>
                <td className="px-4 py-2">
                  <button
                    type="button"
                    onClick={() => removeRow(i)}
                    className="text-slate-400 hover:text-red-500 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-slate-400 text-sm">
                  No team members defined. Add rows below.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <Button type="button" variant="outline" size="sm" onClick={addRow} className="gap-1.5">
        <Plus className="h-3.5 w-3.5" />
        Add Row
      </Button>
    </div>
  )
}

// ─── Generic Section Card ─────────────────────────────────────────────────────

function SectionCard({
  title,
  description,
  icon: Icon,
  entries,
  localValues,
  onFieldChange,
  onSave,
  isSaving,
}: {
  title: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  entries: SettingEntry[]
  localValues: Record<string, string>
  onFieldChange: (key: string, value: string) => void
  onSave: () => void
  isSaving: boolean
}) {
  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-50">
              <Icon className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <CardTitle className="text-base">{title}</CardTitle>
              <CardDescription className="text-xs mt-0.5">{description}</CardDescription>
            </div>
          </div>
          <Button
            size="sm"
            onClick={onSave}
            disabled={isSaving}
            className="gap-1.5"
          >
            {isSaving ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            Save Section
          </Button>
        </div>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {entries.map((entry) => {
            const isWide = entry.data_type === 'json_table' || entry.data_type === 'json_list'
            return (
              <div
                key={entry.key}
                className={`space-y-1.5 ${isWide ? 'sm:col-span-2 xl:col-span-4' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <Label className="text-sm font-medium text-slate-700">{entry.label}</Label>
                  {entry.is_sensitive && (
                    <Badge variant="secondary" className="text-xs px-1.5 py-0 h-4">
                      Sensitive
                    </Badge>
                  )}
                </div>
                {entry.description && (
                  <p className="text-xs text-slate-500">{entry.description}</p>
                )}
                {entry.data_type === 'json_table' ? (
                  <RfpTeamSection
                    entry={entry}
                    localValue={localValues[entry.key] ?? entry.value ?? ''}
                    onChange={onFieldChange}
                  />
                ) : (
                  <SettingField
                    entry={entry}
                    localValue={localValues[entry.key] ?? entry.value ?? ''}
                    onChange={onFieldChange}
                  />
                )}
              </div>
            )
          })}
        </div>
        {entries.length === 0 && (
          <p className="text-sm text-slate-400 italic">No settings in this section.</p>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

const SECTION_META: Record<string, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
  general: { label: 'General', icon: Globe },
  email: { label: 'Email', icon: Mail },
  sharepoint: { label: 'SharePoint', icon: Database },
  dataverse: { label: 'Dataverse', icon: Database },
  flow_urls: { label: 'Flow URLs', icon: Zap },
  rfp_team: { label: 'RFP Team', icon: Users2 },
}

const SECTION_DESCRIPTIONS: Record<string, string> = {
  general: 'Core portal settings: Ariba URL, company name, and company options.',
  email: 'Email recipient addresses for all notification scenarios.',
  sharepoint: 'Azure / SharePoint authentication and folder configuration.',
  dataverse: 'Dataverse environment URL and table names.',
  flow_urls: 'Power Automate HTTP trigger URLs.',
  rfp_team: 'Product-to-person assignment table shown in RFP notification emails.',
}

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const [localValues, setLocalValues] = useState<Record<string, string>>({})
  const [savingSection, setSavingSection] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: api.getSettings,
  })

  // Initialize local values from server data
  useEffect(() => {
    if (data?.data) {
      const initial: Record<string, string> = {}
      for (const entries of Object.values(data.data)) {
        for (const entry of entries) {
          initial[entry.key] = entry.value ?? ''
        }
      }
      setLocalValues(initial)
    }
  }, [data])

  const saveMutation = useMutation({
    mutationFn: (updates: Record<string, string>) => api.saveSettings(updates),
    onSuccess: (result, _variables) => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      if (result.failed && result.failed.length > 0) {
        toast.error(`${result.failed.length} setting(s) failed to save.`)
      } else {
        toast.success(`${result.saved?.length ?? 0} setting(s) saved successfully.`)
      }
      setSavingSection(null)
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to save settings.')
      setSavingSection(null)
    },
  })

  const reloadMutation = useMutation({
    mutationFn: api.reloadSettings,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      toast.success(`Settings reloaded — ${result.loaded} settings active.`)
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to reload settings.')
    },
  })

  const handleFieldChange = useCallback((key: string, value: string) => {
    setLocalValues((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleSaveSection = (sectionKey: string, entries: SettingEntry[]) => {
    setSavingSection(sectionKey)
    const updates: Record<string, string> = {}
    for (const entry of entries) {
      if (localValues[entry.key] !== undefined) {
        updates[entry.key] = localValues[entry.key]
      }
    }
    saveMutation.mutate(updates)
  }

  const sections = data?.data ?? {}
  const sectionKeys = Object.keys(sections)

  return (
    <PageWrapper
      title="System Settings"
      description="View and edit application configuration stored in Dataverse."
      actions={
        <Button
          variant="outline"
          size="sm"
          onClick={() => reloadMutation.mutate()}
          disabled={reloadMutation.isPending}
          className="gap-1.5"
        >
          <RefreshCw className={`h-4 w-4 ${reloadMutation.isPending ? 'animate-spin' : ''}`} />
          Reload Settings
        </Button>
      }
    >
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-4 w-64" />
              </CardHeader>
              <CardContent className="space-y-4">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : sectionKeys.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Settings className="h-12 w-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 font-medium">No settings found</p>
            <p className="text-slate-400 text-sm mt-1">
              Run <code className="bg-slate-100 px-1 rounded">python scripts/seed_settings.py</code> to populate the Dataverse table.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue={sectionKeys[0]} className="space-y-6">
          <TabsList className="flex-wrap h-auto gap-1">
            {sectionKeys.map((sk) => {
              const meta = SECTION_META[sk] ?? { label: sk, icon: Settings }
              const Icon = meta.icon
              return (
                <TabsTrigger key={sk} value={sk} className="gap-1.5 text-xs">
                  <Icon className="h-3.5 w-3.5" />
                  {meta.label}
                </TabsTrigger>
              )
            })}
          </TabsList>

          {sectionKeys.map((sk) => {
            const entries = sections[sk] ?? []
            const meta = SECTION_META[sk] ?? { label: sk, icon: Settings }
            const Icon = meta.icon
            const desc = SECTION_DESCRIPTIONS[sk] ?? ''
            const isSaving = savingSection === sk && saveMutation.isPending

            return (
              <TabsContent key={sk} value={sk}>
                <SectionCard
                  title={meta.label}
                  description={desc}
                  icon={Icon}
                  entries={entries}
                  localValues={localValues}
                  onFieldChange={handleFieldChange}
                  onSave={() => handleSaveSection(sk, entries)}
                  isSaving={isSaving}
                />
              </TabsContent>
            )
          })}
        </Tabs>
      )}
    </PageWrapper>
  )
}
