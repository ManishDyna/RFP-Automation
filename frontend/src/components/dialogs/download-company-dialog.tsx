import { useState } from 'react'
import { toast } from 'sonner'
import { Building, Download, AlertTriangle } from 'lucide-react'

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
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { api } from '@/lib/api'

const COMPANY_OPTIONS = [
  'all',
  'Saudi Electricity Company',
  'SABIC - Saudi Basic Industries Corp.',
  'Aramco e-Marketplace',
  'HADEED - RAJHI STEEL',
]

interface DownloadCompanyDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DownloadCompanyDialog({ open, onOpenChange }: DownloadCompanyDialogProps) {
  const [company, setCompany] = useState('all')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const onSubmit = async () => {
    setIsSubmitting(true)
    try {
      // Pass undefined for 'all' to download from all companies
      await api.downloadRfps(company === 'all' ? undefined : company)
      toast.success('RFP download started successfully')
      handleClose()
    } catch (error: any) {
      toast.error(error.message || 'Failed to start download')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    setCompany('all')
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            Download All RFPs
          </DialogTitle>
          <DialogDescription>
            Select which company portal to download RFPs from.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="company">
              <Building className="inline h-4 w-4 mr-2" />
              Select Company
            </Label>
            <Select value={company} onValueChange={setCompany}>
              <SelectTrigger>
                <SelectValue placeholder="All Companies" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Companies</SelectItem>
                {COMPANY_OPTIONS.filter(c => c !== 'all').map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Select a specific company or "All Companies" to download RFPs from all companies.
            </p>
          </div>

          <Alert variant="warning">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>
              This process will download all available RFPs from the selected company/companies.
            </AlertDescription>
          </Alert>

          <div className="text-sm text-muted-foreground space-y-1">
            <p>This automation will:</p>
            <ul className="list-disc list-inside ml-2 space-y-1">
              <li>Export RFP data from the selected company/companies</li>
              <li>Download individual RFP files</li>
              <li>Store files company-wise in the ALLRFPs folder</li>
              <li>Save RFP information to the database</li>
            </ul>
          </div>

          <p className="text-sm font-medium">
            This process may take a significant amount of time. Do you want to continue?
          </p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={onSubmit} loading={isSubmitting}>
            <Download className="h-4 w-4 mr-2" />
            Yes, Start Download
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
