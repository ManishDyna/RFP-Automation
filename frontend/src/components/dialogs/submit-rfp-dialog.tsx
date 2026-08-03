import { useState, useEffect, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Upload, FileSpreadsheet, File, X, Check, ChevronsUpDown, Cloud, Loader2 } from 'lucide-react'

import { Checkbox } from '@/components/ui/checkbox'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

const submitRfpSchema = z.object({
  rfp_id: z.string().min(1, 'RFP ID is required'),
  company: z.string().min(1, 'Please select a company'),
})

type SubmitRfpFormData = z.infer<typeof submitRfpSchema>

interface SubmitRfpDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialRfpId?: string | null
}

type RfpValidationState =
  | { status: 'idle' }
  | { status: 'validating' }
  | { status: 'valid'; company: string; rfpStatus: string }
  | { status: 'error'; message: string }

export function SubmitRfpDialog({ open, onOpenChange, initialRfpId }: SubmitRfpDialogProps) {
  const [excelFile, setExcelFile] = useState<File | null>(null)
  const [pdfFiles, setPdfFiles] = useState<File[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [rfpValidation, setRfpValidation] = useState<RfpValidationState>({ status: 'idle' })
  const [companyOptions, setCompanyOptions] = useState<string[]>([])
  const [openRfps, setOpenRfps] = useState<Array<{ rfp_id: string; company: string }>>([])
  const [loadingRfps, setLoadingRfps] = useState(false)
  const [comboOpen, setComboOpen] = useState(false)
  const [existingTdsFiles, setExistingTdsFiles] = useState<Array<{ name: string; path: string }>>([])
  const [selectedExistingTds, setSelectedExistingTds] = useState<string[]>([])
  const [loadingTdsFiles, setLoadingTdsFiles] = useState(false)

  const {
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<SubmitRfpFormData>({
    resolver: zodResolver(submitRfpSchema),
    defaultValues: {
      rfp_id: initialRfpId || '',
    },
  })

  useEffect(() => {
    if (!open) return
    api.getCompanyOptions().then((res) => setCompanyOptions(res.options)).catch(() => {})
    setLoadingRfps(true)
    api
      .getDashboardData()
      .then((res: any) => {
        const byCompany = res?.companies_rfps ?? {}
        const rows: Array<{ rfp_id: string; company: string }> = []
        for (const company of Object.keys(byCompany)) {
          const openList = byCompany[company]?.open ?? []
          for (const r of openList) {
            const rfp_id = String(r.RFP_ID ?? '')
            const company_name = String(r.Company_Name ?? company ?? '')
            if (rfp_id && company_name) rows.push({ rfp_id, company: company_name })
          }
        }
        rows.sort(
          (a, b) => a.company.localeCompare(b.company) || a.rfp_id.localeCompare(b.rfp_id),
        )
        setOpenRfps(rows)
      })
      .catch(() => setOpenRfps([]))
      .finally(() => setLoadingRfps(false))
  }, [open])

  const selectRfp = useCallback(
    (rfp: { rfp_id: string; company: string }) => {
      setValue('rfp_id', rfp.rfp_id)
      setValue('company', rfp.company)
      setRfpValidation({ status: 'valid', company: rfp.company, rfpStatus: 'open' })
      setComboOpen(false)
    },
    [setValue],
  )

  useEffect(() => {
    if (!initialRfpId || !open || openRfps.length === 0) return
    const match = openRfps.find(
      (r) => r.rfp_id.toLowerCase() === initialRfpId.toLowerCase(),
    )
    if (match) {
      selectRfp(match)
    } else {
      setValue('rfp_id', initialRfpId)
      setRfpValidation({
        status: 'error',
        message: 'This RFP is not in the Open list — it may be closed or already submitted.',
      })
    }
  }, [initialRfpId, open, openRfps, selectRfp, setValue])

  // When an RFP is validly selected, fetch existing TDS files from SharePoint
  // so the user can pick already-uploaded files instead of re-uploading.
  useEffect(() => {
    if (!open) return
    if (rfpValidation.status !== 'valid') {
      setExistingTdsFiles([])
      setSelectedExistingTds([])
      return
    }
    const rfpId = watch('rfp_id')
    const company = rfpValidation.company
    if (!rfpId || !company) return

    let cancelled = false
    setLoadingTdsFiles(true)
    api
      .listExistingTdsFiles(rfpId, company)
      .then((res) => {
        if (cancelled) return
        const files = res?.files ?? []
        setExistingTdsFiles(files)
        setSelectedExistingTds([])
      })
      .catch(() => {
        if (cancelled) return
        setExistingTdsFiles([])
        setSelectedExistingTds([])
      })
      .finally(() => {
        if (!cancelled) setLoadingTdsFiles(false)
      })

    return () => {
      cancelled = true
    }
  }, [open, rfpValidation, watch])

  const toggleExistingTds = (name: string) => {
    setSelectedExistingTds((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    )
  }

  const handleExcelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setExcelFile(file)
    }
  }

  const handlePdfChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    setPdfFiles((prev) => [...prev, ...files])
  }

  const removePdf = (index: number) => {
    setPdfFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const onSubmit = async (data: SubmitRfpFormData) => {
    // Block submission if RFP is not validated
    if (rfpValidation.status !== 'valid') {
      if (rfpValidation.status === 'error') {
        toast.error(rfpValidation.message)
      } else {
        toast.error('Please enter a valid RFP ID first')
      }
      return
    }

    // Ensure selected company matches the database company
    if (rfpValidation.company && data.company !== rfpValidation.company) {
      toast.error(`This RFP belongs to "${rfpValidation.company}". Please select the correct company.`)
      setValue('company', rfpValidation.company)
      return
    }

    if (!excelFile) {
      toast.error('Please upload an Excel file')
      return
    }

    setIsSubmitting(true)
    try {
      const formData = new FormData()
      formData.append('rfp_id', data.rfp_id)
      formData.append('company', data.company)
      formData.append('excel_file', excelFile)
      pdfFiles.forEach((file) => {
        formData.append('technical_files', file)
      })
      selectedExistingTds.forEach((name) => {
        formData.append('existing_tds_files', name)
      })

      await api.submitRfp(formData)
      toast.success('RFP submission started successfully')
      handleClose()
    } catch (error: any) {
      toast.error(error.message || 'Failed to submit RFP')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    reset()
    setExcelFile(null)
    setPdfFiles([])
    setRfpValidation({ status: 'idle' })
    setExistingTdsFiles([])
    setSelectedExistingTds([])
    onOpenChange(false)
  }

  const isRfpValid = rfpValidation.status === 'valid'
  const isCompanyLocked = isRfpValid && !!rfpValidation.company

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[560px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Submit RFP
          </DialogTitle>
          <DialogDescription>
            Upload the filled RFP Excel file and any technical PDF documents.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 min-w-0">
          <div className="space-y-2">
            <Label htmlFor="rfp_id">RFP ID *</Label>
            <Popover open={comboOpen} onOpenChange={setComboOpen} modal={true}>
              <PopoverTrigger asChild>
                <Button
                  id="rfp_id"
                  type="button"
                  variant="outline"
                  role="combobox"
                  aria-expanded={comboOpen}
                  className="w-full min-w-0 justify-between font-normal"
                >
                  <span className="flex-1 min-w-0 truncate text-left">
                    {watch('rfp_id')
                      ? rfpValidation.status === 'valid' && rfpValidation.company
                        ? `${watch('rfp_id')} — ${rfpValidation.company}`
                        : watch('rfp_id')
                      : 'Select an Open RFP'}
                  </span>
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent
                className="p-0 w-[var(--radix-popover-trigger-width)] max-w-[--radix-popover-trigger-width]"
                align="start"
              >
                <Command>
                  <CommandInput placeholder="Search RFP ID or Company..." />
                  <CommandList>
                    <CommandEmpty>
                      {loadingRfps ? 'Loading open RFPs…' : 'No open RFP found.'}
                    </CommandEmpty>
                    <CommandGroup>
                      {openRfps.map((rfp) => {
                        const isSelected = watch('rfp_id') === rfp.rfp_id
                        return (
                          <CommandItem
                            key={rfp.rfp_id}
                            value={`${rfp.rfp_id} ${rfp.company}`}
                            onSelect={() => selectRfp(rfp)}
                          >
                            <Check
                              className={cn(
                                'mr-2 h-4 w-4 shrink-0',
                                isSelected ? 'opacity-100' : 'opacity-0',
                              )}
                            />
                            <span className="flex-1 min-w-0 truncate">
                              {rfp.rfp_id} — {rfp.company}
                            </span>
                          </CommandItem>
                        )
                      })}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            {rfpValidation.status === 'error' && (
              <p className="text-sm text-destructive">{rfpValidation.message}</p>
            )}
            {rfpValidation.status === 'valid' && (
              <p className="text-sm text-green-600">
                RFP found — Company: {rfpValidation.company}
              </p>
            )}
            {rfpValidation.status === 'idle' && !loadingRfps && openRfps.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No open RFPs available. Please download new RFPs first.
              </p>
            )}
            {rfpValidation.status === 'idle' && (loadingRfps || openRfps.length > 0) && (
              <p className="text-xs text-muted-foreground">
                Choose one of the currently open RFPs.
              </p>
            )}
            {errors.rfp_id && (
              <p className="text-sm text-destructive">{errors.rfp_id.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="company">Company *</Label>
            <Select
              value={watch('company')}
              onValueChange={(value) => {
                if (!isCompanyLocked) {
                  setValue('company', value)
                }
              }}
              disabled={isCompanyLocked}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select company" />
              </SelectTrigger>
              <SelectContent>
                {companyOptions.map((company: string) => (
                  <SelectItem key={company} value={company}>
                    {company}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {isCompanyLocked ? (
              <p className="text-xs text-muted-foreground">
                Company is auto-selected based on the RFP record.
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Automation will run against the selected company portal.
              </p>
            )}
            {errors.company && (
              <p className="text-sm text-destructive">{errors.company.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="excel_file">Upload Excel File *</Label>
            <div className="border-2 border-dashed border-muted rounded-lg p-4 text-center hover:border-primary/50 transition-colors">
              <input
                type="file"
                id="excel_file"
                accept=".xls,.xlsx"
                onChange={handleExcelChange}
                className="hidden"
              />
              <label
                htmlFor="excel_file"
                className="cursor-pointer flex flex-col items-center gap-2 w-full min-w-0"
              >
                <FileSpreadsheet className="h-8 w-8 text-muted-foreground" />
                {excelFile ? (
                  <span className="text-sm font-medium text-primary truncate max-w-full">
                    {excelFile.name}
                  </span>
                ) : (
                  <span className="text-sm text-muted-foreground">
                    Click to upload Excel file (.xls or .xlsx)
                  </span>
                )}
              </label>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="pdf_files">Technical PDF Files (Optional)</Label>
            <div className="border-2 border-dashed border-muted rounded-lg p-4 text-center hover:border-primary/50 transition-colors">
              <input
                type="file"
                id="pdf_files"
                accept=".pdf"
                multiple
                onChange={handlePdfChange}
                className="hidden"
              />
              <label
                htmlFor="pdf_files"
                className="cursor-pointer flex flex-col items-center gap-2"
              >
                <File className="h-8 w-8 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  Click to upload PDF files
                </span>
              </label>
            </div>
            {pdfFiles.length > 0 && (
              <div className="space-y-2 mt-2">
                {pdfFiles.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between gap-2 bg-muted rounded-lg px-3 py-2 min-w-0"
                  >
                    <span className="text-sm truncate flex-1 min-w-0">{file.name}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0"
                      onClick={() => removePdf(index)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Files will be uploaded to the SharePoint TDS-files folder before submission.
            </p>
          </div>

          {rfpValidation.status === 'valid' && (
            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-border" />
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                And / Or pick from SharePoint
              </span>
              <div className="flex-1 h-px bg-border" />
            </div>
          )}

          {rfpValidation.status === 'valid' && (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Label className="flex items-center gap-2">
                  <Cloud className="h-4 w-4" />
                  Existing TDS Files in SharePoint
                </Label>
                {loadingTdsFiles && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Loading…
                  </span>
                )}
              </div>
              {!loadingTdsFiles && existingTdsFiles.length === 0 && (
                <div className="border-2 border-dashed border-muted rounded-lg p-3 text-center">
                  <p className="text-xs text-muted-foreground">
                    No TDS files found in SharePoint folder for this RFP.
                  </p>
                </div>
              )}
              {existingTdsFiles.length > 0 && (
                <div className="border rounded-lg divide-y max-h-44 overflow-y-auto">
                  {existingTdsFiles.map((f) => {
                    const checked = selectedExistingTds.includes(f.name)
                    return (
                      <label
                        key={f.path}
                        className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-muted/50"
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={() => toggleExistingTds(f.name)}
                        />
                        <File className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span className="text-sm truncate flex-1 min-w-0">{f.name}</span>
                      </label>
                    )
                  })}
                </div>
              )}
              {existingTdsFiles.length > 0 ? (
                <p className="text-xs text-muted-foreground">
                  Tick any files already in the SharePoint <span className="font-mono">TDS-files</span> folder
                  you want to reuse ({selectedExistingTds.length}/{existingTdsFiles.length} selected).
                  You can also upload more above — both selected and uploaded files will be used together.
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  You can upload new files above and/or reuse existing ones from SharePoint — both will be used together.
                </p>
              )}
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              loading={isSubmitting}
              disabled={rfpValidation.status === 'error' || rfpValidation.status === 'validating'}
            >
              <Upload className="h-4 w-4 mr-2" />
              Submit RFP
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
