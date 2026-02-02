import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Upload, FileSpreadsheet, File, X } from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { api } from '@/lib/api'

const COMPANY_OPTIONS = ['SEC', 'SABIC', 'Aramco', 'HADEED']

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

export function SubmitRfpDialog({ open, onOpenChange, initialRfpId }: SubmitRfpDialogProps) {
  const [excelFile, setExcelFile] = useState<File | null>(null)
  const [pdfFiles, setPdfFiles] = useState<File[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register,
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

  // Update form when initialRfpId changes
  useEffect(() => {
    if (initialRfpId && open) {
      setValue('rfp_id', initialRfpId)
    }
  }, [initialRfpId, open, setValue])

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
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Submit RFP
          </DialogTitle>
          <DialogDescription>
            Upload the filled RFP Excel file and any technical PDF documents.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="rfp_id">RFP ID *</Label>
            <Input
              id="rfp_id"
              {...register('rfp_id')}
              placeholder="Enter RFP ID (e.g., RFP-C001691810)"
            />
            <p className="text-xs text-muted-foreground">
              Enter the exact ID of the RFP
            </p>
            {errors.rfp_id && (
              <p className="text-sm text-destructive">{errors.rfp_id.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="company">Company *</Label>
            <Select
              value={watch('company')}
              onValueChange={(value) => setValue('company', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select company" />
              </SelectTrigger>
              <SelectContent>
                {COMPANY_OPTIONS.map((company) => (
                  <SelectItem key={company} value={company}>
                    {company}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Automation will run against the selected company portal.
            </p>
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
                className="cursor-pointer flex flex-col items-center gap-2"
              >
                <FileSpreadsheet className="h-8 w-8 text-muted-foreground" />
                {excelFile ? (
                  <span className="text-sm font-medium text-primary">
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
                    className="flex items-center justify-between bg-muted rounded-lg px-3 py-2"
                  >
                    <span className="text-sm truncate">{file.name}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removePdf(index)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Files will be uploaded to SharePoint folder before submission.
            </p>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              <Upload className="h-4 w-4 mr-2" />
              Submit RFP
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
