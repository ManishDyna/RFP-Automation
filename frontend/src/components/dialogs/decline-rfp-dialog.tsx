import { useState, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { XCircle, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'

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

// Company options - should match config.py COMPANY_OPTIONS
const COMPANY_OPTIONS = [
  'Saudi Electricity Company',
  'Aramco e-Marketplace',
  'SABIC - Saudi Basic Industries Corp.',
  'HADEED - RAJHI STEEL',
]

const declineRfpSchema = z.object({
  rfp_title: z.string().min(1, 'RFP title is required'),
  company: z.string().min(1, 'Please select a company'),
})

type DeclineRfpFormData = z.infer<typeof declineRfpSchema>

interface DeclineRfpDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type RfpValidationState =
  | { status: 'idle' }
  | { status: 'validating' }
  | { status: 'valid'; company: string; rfpStatus: string }
  | { status: 'error'; message: string }

export function DeclineRfpDialog({ open, onOpenChange }: DeclineRfpDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [rfpValidation, setRfpValidation] = useState<RfpValidationState>({ status: 'idle' })

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

  const validateRfpId = useCallback(async (rfpId: string) => {
    const trimmed = rfpId.trim()
    if (!trimmed) {
      setRfpValidation({ status: 'idle' })
      return
    }

    setRfpValidation({ status: 'validating' })
    try {
      const result = await api.validateRfp(trimmed)
      setRfpValidation({
        status: 'valid',
        company: result.company,
        rfpStatus: result.status,
      })
      // Auto-set the company from database
      if (result.company) {
        setValue('company', result.company)
      }
    } catch (error: any) {
      setRfpValidation({
        status: 'error',
        message: error.message || 'RFP not found in database. Please download it first.',
      })
      // Clear company selection when RFP is invalid
      setValue('company', '')
    }
  }, [setValue])

  const handleRfpTitleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    validateRfpId(e.target.value)
  }

  const onSubmit = async (data: DeclineRfpFormData) => {
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
    setRfpValidation({ status: 'idle' })
    onOpenChange(false)
  }

  const isRfpValid = rfpValidation.status === 'valid'
  const isCompanyLocked = isRfpValid && !!rfpValidation.company

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
            <div className="relative">
              <Input
                id="rfp_title"
                {...register('rfp_title')}
                placeholder="Enter RFP Title"
                onBlur={handleRfpTitleBlur}
              />
              {rfpValidation.status === 'validating' && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              )}
              {rfpValidation.status === 'valid' && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                </div>
              )}
              {rfpValidation.status === 'error' && (
                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                  <AlertCircle className="h-4 w-4 text-destructive" />
                </div>
              )}
            </div>
            {rfpValidation.status === 'error' && (
              <p className="text-sm text-destructive">{rfpValidation.message}</p>
            )}
            {rfpValidation.status === 'valid' && (
              <p className="text-sm text-green-600">
                RFP found — Company: {rfpValidation.company}
              </p>
            )}
            {rfpValidation.status === 'idle' && (
              <p className="text-xs text-muted-foreground">
                Enter the exact title of the RFP you want to decline
              </p>
            )}
            {errors.rfp_title && (
              <p className="text-sm text-destructive">{errors.rfp_title.message}</p>
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
                {COMPANY_OPTIONS.map((company) => (
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
                Decline automation will run against this company.
              </p>
            )}
            {errors.company && (
              <p className="text-sm text-destructive">{errors.company.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              loading={isSubmitting}
              disabled={rfpValidation.status === 'error' || rfpValidation.status === 'validating'}
            >
              <XCircle className="h-4 w-4 mr-2" />
              Decline RFP
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
