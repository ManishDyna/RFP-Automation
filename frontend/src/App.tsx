import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Toaster } from 'sonner'
import { useAuth } from '@/hooks/use-auth'
import { Sidebar } from '@/components/layout/sidebar'
import { Header } from '@/components/layout/header'
import { cn } from '@/lib/utils'
import { DialogProvider, useDialogs } from '@/contexts/dialog-context'

// Pages
import LoginPage from '@/pages/login'
import DashboardPage from '@/pages/dashboard'
import RfpInsightsPage from '@/pages/rfp-insights'
import LogsPage from '@/pages/logs'
import ProfilePage from '@/pages/profile'
import UserManagementPage from '@/pages/admin/users'
import SapPasswordLogsPage from '@/pages/admin/sap-logs'

// Dialogs
import { SubmitRfpDialog } from '@/components/dialogs/submit-rfp-dialog'
import { DeclineRfpDialog } from '@/components/dialogs/decline-rfp-dialog'
import { DownloadCompanyDialog } from '@/components/dialogs/download-company-dialog'
import { ScheduleDialog } from '@/components/dialogs/schedule-dialog'
import { SapPasswordDialog } from '@/components/dialogs/sap-password-dialog'

function LoadingScreen() {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-50">
      <div className="text-center">
        <div className="relative">
          <div className="w-20 h-20 rounded-2xl bg-white flex items-center justify-center shadow-xl shadow-slate-200/50 mx-auto mb-6 border border-slate-100">
            <img src="/bahra-logo.svg" alt="Bahra Electric" className="h-12 w-auto" />
          </div>
          <div className="absolute -inset-2 rounded-2xl bg-indigo-500/20 animate-ping" />
        </div>
        <h2 className="text-lg font-semibold text-slate-800 mb-1">RFP Portal</h2>
        <p className="text-sm text-slate-500">Loading your workspace...</p>
      </div>
    </div>
  )
}

function ProtectedLayout() {
  const navigate = useNavigate()
  const { isAuthenticated, checkSession, isLoading } = useAuth()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const { submitRfpOpen, submitRfpInitialId, closeSubmitRfpDialog, openSubmitRfpDialog } = useDialogs()

  // Dialog states
  const [declineRfpOpen, setDeclineRfpOpen] = useState(false)
  const [downloadCompanyOpen, setDownloadCompanyOpen] = useState(false)
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [sapPasswordOpen, setSapPasswordOpen] = useState(false)

  useEffect(() => {
    checkSession()
  }, [checkSession])

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/login', { replace: true })
    }
  }, [isAuthenticated, isLoading, navigate])

  if (isLoading) {
    return <LoadingScreen />
  }

  if (!isAuthenticated) {
    return null
  }

  const handleRefresh = () => {
    window.location.reload()
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar
        onDownloadRfps={() => setDownloadCompanyOpen(true)}
        onSubmitRfp={() => openSubmitRfpDialog()}
        onDeclineRfp={() => setDeclineRfpOpen(true)}
        onSchedule={() => setScheduleOpen(true)}
        onChangeSapPassword={() => setSapPasswordOpen(true)}
      />

      <div className={cn(
        'transition-all duration-300',
        sidebarCollapsed ? 'ml-[72px]' : 'ml-[260px]'
      )}>
        <Header
          onDownloadAll={() => setDownloadCompanyOpen(true)}
          onRefresh={handleRefresh}
        />

        <main className="p-6 min-h-[calc(100vh-64px)]">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/dashboard/rfp-insights" element={<RfpInsightsPage />} />
            <Route path="/dashboard/logs" element={<LogsPage />} />
            <Route path="/dashboard/profile" element={<ProfilePage />} />
            <Route path="/dashboard/analytics" element={<div>Analytics Page (Coming Soon)</div>} />
            <Route path="/admin/users" element={<UserManagementPage />} />
            <Route path="/admin/sap-logs" element={<SapPasswordLogsPage />} />
          </Routes>
        </main>
      </div>

      {/* Dialogs */}
      <SubmitRfpDialog
        open={submitRfpOpen}
        onOpenChange={(open) => open ? openSubmitRfpDialog() : closeSubmitRfpDialog()}
        initialRfpId={submitRfpInitialId}
      />
      <DeclineRfpDialog open={declineRfpOpen} onOpenChange={setDeclineRfpOpen} />
      <DownloadCompanyDialog open={downloadCompanyOpen} onOpenChange={setDownloadCompanyOpen} />
      <ScheduleDialog open={scheduleOpen} onOpenChange={setScheduleOpen} />
      <SapPasswordDialog open={sapPasswordOpen} onOpenChange={setSapPasswordOpen} />
    </div>
  )
}

function App() {
  return (
    <DialogProvider>
      <Toaster
        position="top-right"
        richColors
        toastOptions={{
          style: {
            background: 'white',
            border: '1px solid #e2e8f0',
            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
          },
        }}
      />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={<ProtectedLayout />} />
      </Routes>
    </DialogProvider>
  )
}

export default App
