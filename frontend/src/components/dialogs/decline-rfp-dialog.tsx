import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { XCircle, Loader2, ChevronsUpDown, Check } from 'lucide-react'

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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from '@/components/ui/command'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

interface RfpOption {
  RFP_ID: string
  Company_Name: string
}

interface DeclineRfpDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DeclineRfpDialog({ open, onOpenChange }: DeclineRfpDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [rfpOptions, setRfpOptions] = useState<RfpOption[]>([])
  const [isLoadingRfps, setIsLoadingRfps] = useState(false)
  const [selectedRfp, setSelectedRfp] = useState<RfpOption | null>(null)
  const [comboboxOpen, setComboboxOpen] = useState(false)

  // Fetch open RFPs when dialog opens
  useEffect(() => {
    if (!open) return

    const fetchOpenRfps = async () => {
      setIsLoadingRfps(true)
      try {
        const result = await api.getRfpDetails({ status: 'open', limit: 500, offset: 0 })
        setRfpOptions(
          (result.rfps || []).map((rfp: any) => ({
            RFP_ID: rfp.RFP_ID,
            Company_Name: rfp.Company_Name || 'Unknown',
          }))
        )
      } catch {
        toast.error('Failed to load RFPs')
      } finally {
        setIsLoadingRfps(false)
      }
    }

    fetchOpenRfps()
  }, [open])

  const onSubmit = async () => {
    if (!selectedRfp) {
      toast.error('Please select an RFP')
      return
    }

    setIsSubmitting(true)
    try {
      await api.declineRfp(selectedRfp.RFP_ID, selectedRfp.Company_Name)
      toast.success('RFP decline initiated successfully')
      handleClose()
    } catch (error: any) {
      toast.error(error.message || 'Failed to decline RFP')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    setSelectedRfp(null)
    setComboboxOpen(false)
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
            Select the RFP you want to decline participation for.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>RFP *</Label>
            <Popover open={comboboxOpen} onOpenChange={setComboboxOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  aria-expanded={comboboxOpen}
                  className="w-full justify-between font-normal h-auto min-h-10"
                  disabled={isLoadingRfps}
                >
                  {isLoadingRfps ? (
                    <span className="flex items-center gap-2 text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading RFPs...
                    </span>
                  ) : selectedRfp ? (
                    <span className="text-left truncate block overflow-hidden text-ellipsis whitespace-nowrap max-w-[calc(100%-2rem)]">
                      {selectedRfp.RFP_ID}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">Select an RFP...</span>
                  )}
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
                <Command>
                  <CommandInput placeholder="Search RFPs..." />
                  <CommandList>
                    <CommandEmpty>No RFPs found.</CommandEmpty>
                    <CommandGroup>
                      {rfpOptions.map((rfp) => (
                        <CommandItem
                          key={rfp.RFP_ID}
                          value={`${rfp.RFP_ID} ${rfp.Company_Name}`}
                          onSelect={() => {
                            setSelectedRfp(rfp)
                            setComboboxOpen(false)
                          }}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              selectedRfp?.RFP_ID === rfp.RFP_ID
                                ? "opacity-100"
                                : "opacity-0"
                            )}
                          />
                          <div className="flex flex-col">
                            <span className="text-sm">{rfp.RFP_ID}</span>
                            <span className="text-xs text-muted-foreground">
                              {rfp.Company_Name}
                            </span>
                          </div>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            <p className="text-xs text-muted-foreground">
              {rfpOptions.length > 0
                ? `${rfpOptions.length} open RFP(s) available`
                : isLoadingRfps
                  ? 'Fetching open RFPs...'
                  : 'No open RFPs found'}
            </p>
          </div>

          {selectedRfp && (
            <div className="space-y-2">
              <Label>Company</Label>
              <div className="rounded-md border px-3 py-2 text-sm bg-muted/50">
                {selectedRfp.Company_Name}
              </div>
              <p className="text-xs text-muted-foreground">
                Company is auto-selected based on the RFP record.
              </p>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              loading={isSubmitting}
              disabled={!selectedRfp}
              onClick={onSubmit}
            >
              <XCircle className="h-4 w-4 mr-2" />
              Decline RFP
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  )
}
