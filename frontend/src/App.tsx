import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useEffect, useState, Suspense, lazy } from 'react'
import { Toaster } from 'sonner'
import { useAuth } from '@/hooks/use-auth'
import { Sidebar } from '@/components/layout/sidebar'
import { Header } from '@/components/layout/header'
import { cn } from '@/lib/utils'
import { DialogProvider, useDialogs } from '@/contexts/dialog-context'

// Lazy-loaded pages for code splitting (only load when route is accessed)
const LoginPage = lazy(() => import('@/pages/login'))
const DashboardPage = lazy(() => import('@/pages/dashboard'))
const RfpInsightsPage = lazy(() => import('@/pages/rfp-insights'))
const LogsPage = lazy(() => import('@/pages/logs'))
const ProfilePage = lazy(() => import('@/pages/profile'))
const AnalyticsPage = lazy(() => import('@/pages/analytics'))
const UserManagementPage = lazy(() => import('@/pages/admin/users'))
const RoleManagementPage = lazy(() => import('@/pages/admin/roles'))
const AuditLogsPage = lazy(() => import('@/pages/admin/audit-logs'))
const SapPasswordLogsPage = lazy(() => import('@/pages/admin/sap-logs'))
const MaterialInsightsPage = lazy(() => import('@/pages/material-insights'))

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

// Lightweight page loader for route transitions (faster than full LoadingScreen)
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-3 border-slate-200 border-t-blue-500 rounded-full animate-spin" />
        <p className="text-sm text-slate-500">Loading...</p>
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
  const [downloadMode, setDownloadMode] = useState<'open' | 'all'>('all')
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
        onDownloadRfps={() => { setDownloadMode('open'); setDownloadCompanyOpen(true) }}
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
          onDownloadAll={() => { setDownloadMode('all'); setDownloadCompanyOpen(true) }}
          onRefresh={handleRefresh}
        />

        <main className="p-6 min-h-[calc(100vh-64px)]">
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/dashboard/rfp-insights" element={<RfpInsightsPage />} />
              <Route path="/dashboard/material-insights" element={<MaterialInsightsPage />} />
              <Route path="/dashboard/logs" element={<LogsPage />} />
              <Route path="/dashboard/profile" element={<ProfilePage />} />
              <Route path="/dashboard/analytics" element={<AnalyticsPage />} />
              <Route path="/admin/users" element={<UserManagementPage />} />
              <Route path="/admin/roles" element={<RoleManagementPage />} />
              <Route path="/admin/audit-logs" element={<AuditLogsPage />} />
              <Route path="/admin/sap-logs" element={<SapPasswordLogsPage />} />
            </Routes>
          </Suspense>
        </main>
      </div>

      {/* Dialogs */}
      <SubmitRfpDialog
        open={submitRfpOpen}
        onOpenChange={(open) => open ? openSubmitRfpDialog() : closeSubmitRfpDialog()}
        initialRfpId={submitRfpInitialId}
      />
      <DeclineRfpDialog open={declineRfpOpen} onOpenChange={setDeclineRfpOpen} />
      <DownloadCompanyDialog open={downloadCompanyOpen} onOpenChange={setDownloadCompanyOpen} mode={downloadMode} />
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
      <Suspense fallback={<LoadingScreen />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/*" element={<ProtectedLayout />} />
        </Routes>
      </Suspense>
    </DialogProvider>
  )
}

export default App
