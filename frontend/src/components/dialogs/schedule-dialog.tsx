import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Calendar, Save, Loader2 } from 'lucide-react'

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

// Full Power Automate / Logic Apps Recurrence time-zone list.
// Values are Windows time-zone IDs (accepted as-is by the PA Recurrence trigger).
const TIMEZONE_OPTIONS = [
  { value: 'Dateline Standard Time', label: '(UTC-12:00) International Date Line West' },
  { value: 'UTC-11', label: '(UTC-11:00) Coordinated Universal Time-11' },
  { value: 'Aleutian Standard Time', label: '(UTC-10:00) Aleutian Islands' },
  { value: 'Hawaiian Standard Time', label: '(UTC-10:00) Hawaii' },
  { value: 'Marquesas Standard Time', label: '(UTC-09:30) Marquesas Islands' },
  { value: 'Alaskan Standard Time', label: '(UTC-09:00) Alaska' },
  { value: 'UTC-09', label: '(UTC-09:00) Coordinated Universal Time-09' },
  { value: 'Pacific Standard Time (Mexico)', label: '(UTC-08:00) Baja California' },
  { value: 'UTC-08', label: '(UTC-08:00) Coordinated Universal Time-08' },
  { value: 'Pacific Standard Time', label: '(UTC-08:00) Pacific Time (US & Canada)' },
  { value: 'US Mountain Standard Time', label: '(UTC-07:00) Arizona' },
  { value: 'Mountain Standard Time (Mexico)', label: '(UTC-07:00) Chihuahua, La Paz, Mazatlan' },
  { value: 'Mountain Standard Time', label: '(UTC-07:00) Mountain Time (US & Canada)' },
  { value: 'Yukon Standard Time', label: '(UTC-07:00) Yukon' },
  { value: 'Central America Standard Time', label: '(UTC-06:00) Central America' },
  { value: 'Central Standard Time', label: '(UTC-06:00) Central Time (US & Canada)' },
  { value: 'Easter Island Standard Time', label: '(UTC-06:00) Easter Island' },
  { value: 'Central Standard Time (Mexico)', label: '(UTC-06:00) Guadalajara, Mexico City, Monterrey' },
  { value: 'Canada Central Standard Time', label: '(UTC-06:00) Saskatchewan' },
  { value: 'SA Pacific Standard Time', label: '(UTC-05:00) Bogota, Lima, Quito, Rio Branco' },
  { value: 'Eastern Standard Time (Mexico)', label: '(UTC-05:00) Chetumal' },
  { value: 'Eastern Standard Time', label: '(UTC-05:00) Eastern Time (US & Canada)' },
  { value: 'Haiti Standard Time', label: '(UTC-05:00) Haiti' },
  { value: 'Cuba Standard Time', label: '(UTC-05:00) Havana' },
  { value: 'US Eastern Standard Time', label: '(UTC-05:00) Indiana (East)' },
  { value: 'Turks And Caicos Standard Time', label: '(UTC-05:00) Turks and Caicos' },
  { value: 'Paraguay Standard Time', label: '(UTC-04:00) Asuncion' },
  { value: 'Atlantic Standard Time', label: '(UTC-04:00) Atlantic Time (Canada)' },
  { value: 'Venezuela Standard Time', label: '(UTC-04:00) Caracas' },
  { value: 'Central Brazilian Standard Time', label: '(UTC-04:00) Cuiaba' },
  { value: 'SA Western Standard Time', label: '(UTC-04:00) Georgetown, La Paz, Manaus, San Juan' },
  { value: 'Pacific SA Standard Time', label: '(UTC-04:00) Santiago' },
  { value: 'Newfoundland Standard Time', label: '(UTC-03:30) Newfoundland' },
  { value: 'Tocantins Standard Time', label: '(UTC-03:00) Araguaina' },
  { value: 'E. South America Standard Time', label: '(UTC-03:00) Brasilia' },
  { value: 'SA Eastern Standard Time', label: '(UTC-03:00) Cayenne, Fortaleza' },
  { value: 'Argentina Standard Time', label: '(UTC-03:00) City of Buenos Aires' },
  { value: 'Greenland Standard Time', label: '(UTC-03:00) Greenland' },
  { value: 'Montevideo Standard Time', label: '(UTC-03:00) Montevideo' },
  { value: 'Magallanes Standard Time', label: '(UTC-03:00) Punta Arenas' },
  { value: 'Saint Pierre Standard Time', label: '(UTC-03:00) Saint Pierre and Miquelon' },
  { value: 'Bahia Standard Time', label: '(UTC-03:00) Salvador' },
  { value: 'UTC-02', label: '(UTC-02:00) Coordinated Universal Time-02' },
  { value: 'Mid-Atlantic Standard Time', label: '(UTC-02:00) Mid-Atlantic - Old' },
  { value: 'Azores Standard Time', label: '(UTC-01:00) Azores' },
  { value: 'Cape Verde Standard Time', label: '(UTC-01:00) Cabo Verde Is.' },
  { value: 'UTC', label: '(UTC) Coordinated Universal Time' },
  { value: 'GMT Standard Time', label: '(UTC+00:00) Dublin, Edinburgh, Lisbon, London' },
  { value: 'Greenwich Standard Time', label: '(UTC+00:00) Monrovia, Reykjavik' },
  { value: 'Sao Tome Standard Time', label: '(UTC+00:00) Sao Tome' },
  { value: 'Morocco Standard Time', label: '(UTC+01:00) Casablanca' },
  { value: 'W. Europe Standard Time', label: '(UTC+01:00) Amsterdam, Berlin, Bern, Rome, Stockholm, Vienna' },
  { value: 'Central Europe Standard Time', label: '(UTC+01:00) Belgrade, Bratislava, Budapest, Ljubljana, Prague' },
  { value: 'Romance Standard Time', label: '(UTC+01:00) Brussels, Copenhagen, Madrid, Paris' },
  { value: 'Central European Standard Time', label: '(UTC+01:00) Sarajevo, Skopje, Warsaw, Zagreb' },
  { value: 'W. Central Africa Standard Time', label: '(UTC+01:00) West Central Africa' },
  { value: 'Jordan Standard Time', label: '(UTC+03:00) Amman' },
  { value: 'GTB Standard Time', label: '(UTC+02:00) Athens, Bucharest' },
  { value: 'Middle East Standard Time', label: '(UTC+02:00) Beirut' },
  { value: 'Egypt Standard Time', label: '(UTC+02:00) Cairo' },
  { value: 'E. Europe Standard Time', label: '(UTC+02:00) Chisinau' },
  { value: 'Syria Standard Time', label: '(UTC+03:00) Damascus' },
  { value: 'West Bank Standard Time', label: '(UTC+02:00) Gaza, Hebron' },
  { value: 'South Africa Standard Time', label: '(UTC+02:00) Harare, Pretoria' },
  { value: 'FLE Standard Time', label: '(UTC+02:00) Helsinki, Kyiv, Riga, Sofia, Tallinn, Vilnius' },
  { value: 'Israel Standard Time', label: '(UTC+02:00) Jerusalem' },
  { value: 'South Sudan Standard Time', label: '(UTC+02:00) Juba' },
  { value: 'Kaliningrad Standard Time', label: '(UTC+02:00) Kaliningrad' },
  { value: 'Sudan Standard Time', label: '(UTC+02:00) Khartoum' },
  { value: 'Libya Standard Time', label: '(UTC+02:00) Tripoli' },
  { value: 'Namibia Standard Time', label: '(UTC+02:00) Windhoek' },
  { value: 'Arabic Standard Time', label: '(UTC+03:00) Baghdad' },
  { value: 'Turkey Standard Time', label: '(UTC+03:00) Istanbul' },
  { value: 'Arab Standard Time', label: '(UTC+03:00) Kuwait, Riyadh' },
  { value: 'Belarus Standard Time', label: '(UTC+03:00) Minsk' },
  { value: 'Russian Standard Time', label: '(UTC+03:00) Moscow, St. Petersburg' },
  { value: 'E. Africa Standard Time', label: '(UTC+03:00) Nairobi' },
  { value: 'Volgograd Standard Time', label: '(UTC+03:00) Volgograd' },
  { value: 'Iran Standard Time', label: '(UTC+03:30) Tehran' },
  { value: 'Arabian Standard Time', label: '(UTC+04:00) Abu Dhabi, Muscat' },
  { value: 'Astrakhan Standard Time', label: '(UTC+04:00) Astrakhan, Ulyanovsk' },
  { value: 'Azerbaijan Standard Time', label: '(UTC+04:00) Baku' },
  { value: 'Russia Time Zone 3', label: '(UTC+04:00) Izhevsk, Samara' },
  { value: 'Mauritius Standard Time', label: '(UTC+04:00) Port Louis' },
  { value: 'Saratov Standard Time', label: '(UTC+04:00) Saratov' },
  { value: 'Georgian Standard Time', label: '(UTC+04:00) Tbilisi' },
  { value: 'Caucasus Standard Time', label: '(UTC+04:00) Yerevan' },
  { value: 'Afghanistan Standard Time', label: '(UTC+04:30) Kabul' },
  { value: 'West Asia Standard Time', label: '(UTC+05:00) Ashgabat, Tashkent' },
  { value: 'Ekaterinburg Standard Time', label: '(UTC+05:00) Ekaterinburg' },
  { value: 'Pakistan Standard Time', label: '(UTC+05:00) Islamabad, Karachi' },
  { value: 'Qyzylorda Standard Time', label: '(UTC+05:00) Qyzylorda' },
  { value: 'India Standard Time', label: '(UTC+05:30) Chennai, Kolkata, Mumbai, New Delhi' },
  { value: 'Sri Lanka Standard Time', label: '(UTC+05:30) Sri Jayawardenepura' },
  { value: 'Nepal Standard Time', label: '(UTC+05:45) Kathmandu' },
  { value: 'Central Asia Standard Time', label: '(UTC+06:00) Astana' },
  { value: 'Bangladesh Standard Time', label: '(UTC+06:00) Dhaka' },
  { value: 'Omsk Standard Time', label: '(UTC+06:00) Omsk' },
  { value: 'Myanmar Standard Time', label: '(UTC+06:30) Yangon (Rangoon)' },
  { value: 'SE Asia Standard Time', label: '(UTC+07:00) Bangkok, Hanoi, Jakarta' },
  { value: 'Altai Standard Time', label: '(UTC+07:00) Barnaul, Gorno-Altaysk' },
  { value: 'W. Mongolia Standard Time', label: '(UTC+07:00) Hovd' },
  { value: 'North Asia Standard Time', label: '(UTC+07:00) Krasnoyarsk' },
  { value: 'N. Central Asia Standard Time', label: '(UTC+07:00) Novosibirsk' },
  { value: 'Tomsk Standard Time', label: '(UTC+07:00) Tomsk' },
  { value: 'China Standard Time', label: '(UTC+08:00) Beijing, Chongqing, Hong Kong, Urumqi' },
  { value: 'North Asia East Standard Time', label: '(UTC+08:00) Irkutsk' },
  { value: 'Singapore Standard Time', label: '(UTC+08:00) Kuala Lumpur, Singapore' },
  { value: 'W. Australia Standard Time', label: '(UTC+08:00) Perth' },
  { value: 'Taipei Standard Time', label: '(UTC+08:00) Taipei' },
  { value: 'Ulaanbaatar Standard Time', label: '(UTC+08:00) Ulaanbaatar' },
  { value: 'Aus Central W. Standard Time', label: '(UTC+08:45) Eucla' },
  { value: 'Transbaikal Standard Time', label: '(UTC+09:00) Chita' },
  { value: 'Tokyo Standard Time', label: '(UTC+09:00) Osaka, Sapporo, Tokyo' },
  { value: 'North Korea Standard Time', label: '(UTC+09:00) Pyongyang' },
  { value: 'Korea Standard Time', label: '(UTC+09:00) Seoul' },
  { value: 'Yakutsk Standard Time', label: '(UTC+09:00) Yakutsk' },
  { value: 'Cen. Australia Standard Time', label: '(UTC+09:30) Adelaide' },
  { value: 'AUS Central Standard Time', label: '(UTC+09:30) Darwin' },
  { value: 'E. Australia Standard Time', label: '(UTC+10:00) Brisbane' },
  { value: 'AUS Eastern Standard Time', label: '(UTC+10:00) Canberra, Melbourne, Sydney' },
  { value: 'West Pacific Standard Time', label: '(UTC+10:00) Guam, Port Moresby' },
  { value: 'Tasmania Standard Time', label: '(UTC+10:00) Hobart' },
  { value: 'Vladivostok Standard Time', label: '(UTC+10:00) Vladivostok' },
  { value: 'Lord Howe Standard Time', label: '(UTC+10:30) Lord Howe Island' },
  { value: 'Bougainville Standard Time', label: '(UTC+11:00) Bougainville Island' },
  { value: 'Russia Time Zone 10', label: '(UTC+11:00) Chokurdakh' },
  { value: 'Magadan Standard Time', label: '(UTC+11:00) Magadan' },
  { value: 'Norfolk Standard Time', label: '(UTC+11:00) Norfolk Island' },
  { value: 'Sakhalin Standard Time', label: '(UTC+11:00) Sakhalin' },
  { value: 'Central Pacific Standard Time', label: '(UTC+11:00) Solomon Is., New Caledonia' },
  { value: 'Russia Time Zone 11', label: '(UTC+12:00) Anadyr, Petropavlovsk-Kamchatsky' },
  { value: 'New Zealand Standard Time', label: '(UTC+12:00) Auckland, Wellington' },
  { value: 'UTC+12', label: '(UTC+12:00) Coordinated Universal Time+12' },
  { value: 'Fiji Standard Time', label: '(UTC+12:00) Fiji' },
  { value: 'Kamchatka Standard Time', label: '(UTC+12:00) Petropavlovsk-Kamchatsky - Old' },
  { value: 'Chatham Islands Standard Time', label: '(UTC+12:45) Chatham Islands' },
  { value: 'UTC+13', label: '(UTC+13:00) Coordinated Universal Time+13' },
  { value: 'Tonga Standard Time', label: "(UTC+13:00) Nuku'alofa" },
  { value: 'Samoa Standard Time', label: '(UTC+13:00) Samoa' },
  { value: 'Line Islands Standard Time', label: '(UTC+14:00) Kiritimati Island' },
]

// Legacy IANA → Windows tz ID (for schedules saved before the full list).
const LEGACY_TZ_MAP: Record<string, string> = {
  'Asia/Kolkata': 'India Standard Time',
  'Asia/Riyadh': 'Arab Standard Time',
  'Europe/London': 'GMT Standard Time',
  'Europe/Berlin': 'W. Europe Standard Time',
}

export function ScheduleDialog({ open, onOpenChange }: ScheduleDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
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
      timezone: 'India Standard Time',
      max_concurrency: 1,
    },
  })

  // Fetch existing schedule when dialog opens
  useEffect(() => {
    if (open) {
      setIsLoading(true)
      api.getSchedule()
        .then((response) => {
          if (response.ok && response.data) {
            const data = response.data
            // Populate form with existing schedule data
            if (data.interval) setValue('interval', data.interval)
            if (data.frequency) setValue('frequency', data.frequency)
            if (data.timezone) {
              setValue('timezone', LEGACY_TZ_MAP[data.timezone] || data.timezone)
            }
            if (data.start_time) setValue('start_time', data.start_time)
            if (data.max_concurrency) {
              setValue('max_concurrency', data.max_concurrency)
              setShowAdvanced(true)
            }
            if (data.notes) {
              setValue('notes', data.notes)
              setShowAdvanced(true)
            }
          }
        })
        .catch((error) => {
          console.error('Failed to fetch schedule:', error)
        })
        .finally(() => {
          setIsLoading(false)
        })
    }
  }, [open, setValue])

  const onSubmit = async (data: ScheduleFormData) => {
    setIsSubmitting(true)
    try {
      const response = (await api.saveSchedule(data)) as {
        ok?: boolean
        pa_synced?: boolean
        pa_message?: string
      }
      if (response?.pa_synced === false) {
        toast.warning('Schedule saved, but Power Automate flow was not updated', {
          description: response.pa_message || 'Check backend logs for details.',
        })
      } else {
        toast.success('Schedule saved and Power Automate flow updated')
      }
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

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
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
        )}
      </DialogContent>
    </Dialog>
  )
}
