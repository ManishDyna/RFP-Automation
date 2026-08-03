import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Send, UserCheck } from 'lucide-react'

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
import { api } from '@/lib/api'

interface DelegateRfpDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  rfpId: string
  product: string
  currentEmail: string
  currentName: string
  onSuccess: () => void
}

export function DelegateRfpDialog({
  open,
  onOpenChange,
  rfpId,
  product,
  currentEmail,
  currentName,
  onSuccess,
}: DelegateRfpDialogProps) {
  const [newEmail, setNewEmail] = useState('')
  const [newName, setNewName] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (open) {
      setNewEmail('')
      setNewName('')
    }
  }, [open])

  const handleClose = () => {
    if (isSubmitting) return
    onOpenChange(false)
  }

  const onSubmit = async () => {
    const email = newEmail.trim()
    const name = newName.trim()

    if (!email || !email.includes('@')) {
      toast.error('Please enter a valid new email address.')
      return
    }
    if (!name) {
      toast.error('Please enter the new recipient name.')
      return
    }
    if (email.toLowerCase() === currentEmail.toLowerCase()) {
      toast.error('New email must differ from the current email.')
      return
    }

    setIsSubmitting(true)
    try {
      const result = await api.delegateOpenRfp(rfpId, {
        product,
        original_email: currentEmail,
        new_email: email,
        new_name: name,
      })
      if (result.email_status === 'Sent') {
        toast.success(`Delegated to ${email} · email sent.`)
      } else {
        toast.warning(
          `Delegated to ${email}, but email send failed: ${result.error || 'unknown error'}`
        )
      }
      onSuccess()
      onOpenChange(false)
    } catch (error: any) {
      toast.error(error?.message || 'Failed to delegate RFP.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserCheck className="h-5 w-5" />
            Delegate RFP
          </DialogTitle>
          <DialogDescription>
            Hand off this product line ({product}) to a different recipient for
            this RFP only. The new person will get the same actionable card
            email. The master RFP team is not affected.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Current Email</Label>
            <Input
              value={currentEmail}
              readOnly
              className="bg-muted/50 cursor-not-allowed"
            />
            {currentName && (
              <p className="text-xs text-muted-foreground">{currentName}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="delegate-new-email">New Email *</Label>
            <Input
              id="delegate-new-email"
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              placeholder="new.recipient@company.com"
              disabled={isSubmitting}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="delegate-new-name">New Name *</Label>
            <Input
              id="delegate-new-name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Full name"
              disabled={isSubmitting}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={onSubmit}
              loading={isSubmitting}
              disabled={!newEmail.trim() || !newName.trim()}
            >
              <Send className="h-4 w-4 mr-2" />
              Save & Send Email
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  )
}
