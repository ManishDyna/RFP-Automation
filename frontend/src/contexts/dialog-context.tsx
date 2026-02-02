import { createContext, useContext, useState, ReactNode } from 'react'

interface DialogContextType {
  submitRfpOpen: boolean
  setSubmitRfpOpen: (open: boolean) => void
  submitRfpInitialId: string | null
  openSubmitRfpDialog: (rfpId?: string) => void
  closeSubmitRfpDialog: () => void
}

const DialogContext = createContext<DialogContextType | undefined>(undefined)

export function DialogProvider({ children }: { children: ReactNode }) {
  const [submitRfpOpen, setSubmitRfpOpen] = useState(false)
  const [submitRfpInitialId, setSubmitRfpInitialId] = useState<string | null>(null)

  const openSubmitRfpDialog = (rfpId?: string) => {
    setSubmitRfpInitialId(rfpId || null)
    setSubmitRfpOpen(true)
  }

  const closeSubmitRfpDialog = () => {
    setSubmitRfpOpen(false)
    setSubmitRfpInitialId(null)
  }

  return (
    <DialogContext.Provider
      value={{
        submitRfpOpen,
        setSubmitRfpOpen,
        submitRfpInitialId,
        openSubmitRfpDialog,
        closeSubmitRfpDialog,
      }}
    >
      {children}
    </DialogContext.Provider>
  )
}

export function useDialogs() {
  const context = useContext(DialogContext)
  if (context === undefined) {
    throw new Error('useDialogs must be used within a DialogProvider')
  }
  return context
}
