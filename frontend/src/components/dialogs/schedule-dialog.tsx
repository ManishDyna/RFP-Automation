import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Calendar, Save } from 'lucide-react'

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

const scheduleSchema = z.object({
  interval: z.number().min(1, 'Interval must be at least 1'),
  frequency: z.string().min(1, 'Please select a frequency'),
  timezone: z.string().min(1, 'Please select a timezone'),
  start_time: z.string().optional(),
  max_concurrency: z.number().min(1).optional(),
  notes: z.string().optional(),
})

type ScheduleFormData = z.infer<typeof scheduleSchema>

interface ScheduleDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const FREQUENCY_OPTIONS = [
  { value: 'Minute', label: 'Minute' },
  { value: 'Hour', label: 'Hour' },
  { value: 'Day', label: 'Day' },
  { value: 'Week', label: 'Week' },
  { value: 'Month', label: 'Month' },
]

const TIMEZONE_OPTIONS = [
  { value: 'Asia/Kolkata', label: '(UTC+05:30) Chennai, Kolkata, Mumbai, New Delhi' },
  { value: 'Asia/Riyadh', label: '(UTC+03:00) Kuwait, Riyadh' },
  { value: 'UTC', label: '(UTC+00:00) Coordinated Universal Time' },
  { value: 'Europe/London', label: '(UTC+00:00) Dublin, Edinburgh, Lisbon, London' },
  { value: 'Europe/Berlin', label: '(UTC+01:00) Amsterdam, Berlin, Rome, Stockholm' },
]

export function ScheduleDialog({ open, onOpenChange }: ScheduleDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<ScheduleFormData>({
    resolver: zodResolver(scheduleSchema),
    defaultValues: {
      interval: 6,
      frequency: 'Hour',
      timezone: 'Asia/Kolkata',
      max_concurrency: 1,
    },
  })

  const onSubmit = async (data: ScheduleFormData) => {
    setIsSubmitting(true)
    try {
      await api.saveSchedule(data)
      toast.success('Schedule saved successfully')
      handleClose()
    } catch (error: any) {
      toast.error(error.message || 'Failed to save schedule')
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
      <DialogContent className="sm:max-w-[550px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Schedule Automation
          </DialogTitle>
          <DialogDescription>
            Configure automated RFP download schedule.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="interval">Interval</Label>
              <Input
                id="interval"
                type="number"
                min={1}
                {...register('interval', { valueAsNumber: true })}
              />
              {errors.interval && (
                <p className="text-sm text-destructive">{errors.interval.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="frequency">Frequency</Label>
              <Select
                value={watch('frequency')}
                onValueChange={(value) => setValue('frequency', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select frequency" />
                </SelectTrigger>
                <SelectContent>
                  {FREQUENCY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="timezone">Time zone</Label>
            <Select
              value={watch('timezone')}
              onValueChange={(value) => setValue('timezone', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select timezone" />
              </SelectTrigger>
              <SelectContent>
                {TIMEZONE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="start_time">Start time (optional)</Label>
            <Input
              id="start_time"
              type="datetime-local"
              {...register('start_time')}
            />
            <p className="text-xs text-muted-foreground">
              When the first run should start.
            </p>
          </div>

          <button
            type="button"
            className="text-sm text-primary hover:underline"
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? 'Hide' : 'Show'} advanced options
          </button>

          {showAdvanced && (
            <div className="grid grid-cols-2 gap-4 pt-2">
              <div className="space-y-2">
                <Label htmlFor="max_concurrency">Max concurrency</Label>
                <Input
                  id="max_concurrency"
                  type="number"
                  min={1}
                  {...register('max_concurrency', { valueAsNumber: true })}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="notes">Notes</Label>
                <Input
                  id="notes"
                  {...register('notes')}
                  placeholder="Optional note"
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              <Save className="h-4 w-4 mr-2" />
              Save Schedule
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
