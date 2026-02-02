import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { XCircle } from 'lucide-react'

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

const declineRfpSchema = z.object({
  rfp_title: z.string().min(1, 'RFP title is required'),
  company: z.string().min(1, 'Please select a company'),
})

type DeclineRfpFormData = z.infer<typeof declineRfpSchema>

interface DeclineRfpDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DeclineRfpDialog({ open, onOpenChange }: DeclineRfpDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<DeclineRfpFormData>({
    resolver: zodResolver(declineRfpSchema),
  })

  const onSubmit = async (data: DeclineRfpFormData) => {
    setIsSubmitting(true)
    try {
      await api.declineRfp(data.rfp_title, data.company)
      toast.success('RFP decline initiated successfully')
      handleClose()
    } catch (error: any) {
      toast.error(error.message || 'Failed to decline RFP')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    reset()
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <XCircle className="h-5 w-5" />
            Decline RFP
          </DialogTitle>
          <DialogDescription>
            Enter the RFP details to decline participation.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="rfp_title">RFP Title *</Label>
            <Input
              id="rfp_title"
              {...register('rfp_title')}
              placeholder="Enter RFP Title"
            />
            <p className="text-xs text-muted-foreground">
              Enter the exact title of the RFP you want to decline
            </p>
            {errors.rfp_title && (
              <p className="text-sm text-destructive">{errors.rfp_title.message}</p>
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
              Decline automation will run against this company.
            </p>
            {errors.company && (
              <p className="text-sm text-destructive">{errors.company.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" variant="destructive" loading={isSubmitting}>
              <XCircle className="h-4 w-4 mr-2" />
              Decline RFP
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
