import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  FileSearch,
  ScrollText,
  Users,
  KeyRound,
  BarChart3,
  Download,
  Send,
  Ban,
  Clock,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
  Shield,
  Activity,
  Package,
  Database,
  SlidersHorizontal,
  MailWarning,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip'
import { useHasPermission } from '@/hooks/use-auth'
import { useAutomationStatus } from '@/hooks/use-automation'

interface SidebarProps {
  onDownloadRfps: () => void
  onSubmitRfp: () => void
  onDeclineRfp: () => void
  onSchedule: () => void
  onChangeSapPassword: () => void
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
}

export function Sidebar({
  onDownloadRfps,
  onSubmitRfp,
  onDeclineRfp,
  onSchedule,
  onChangeSapPassword,
  collapsed,
  onCollapsedChange,
}: SidebarProps) {
  const location = useLocation()
  // Main menu permissions
  const canViewDashboard = useHasPermission('dashboard.view')
  const canViewRfpInsights = useHasPermission('rfp.view')
  const canViewMaterialInsights = useHasPermission('material_insights.view')
  const canViewLogs = useHasPermission('logs.view')
  const canViewOpenRfp = useHasPermission('rfp.open.view')

  // RFP operation permissions
  const canDownloadRfp = useHasPermission('rfp.download')
  const canSubmitRfp = useHasPermission('rfp.submit')
  const canDeclineRfp = useHasPermission('rfp.decline')

  // Admin section permissions
  const canManageUsers = useHasPermission('user_management.view')
  const canManageRoles = useHasPermission('role_management.view')
  const canViewAuditLogs = useHasPermission('audit_logs.view')
  const canViewAnalytics = useHasPermission('analytics.view')
  const canViewSapLogs = useHasPermission('sap_password.view')
  const canSchedule = useHasPermission('schedule_automation.manage')
  const canChangeSapPassword = useHasPermission('sap_password.change')
  const canViewMaterialMaster = useHasPermission('material_master.view')
  const canViewKeywordMaster = useHasPermission('keyword_master.view')
  const canViewRfpTeam = useHasPermission('rfp_team.view')
  const canViewColumnConfig = useHasPermission('column_config.view')
  const canManageMasterData = canViewMaterialMaster || canViewKeywordMaster || canViewRfpTeam || canViewColumnConfig
  const canViewSettings = useHasPermission('system_settings.view')
  const showAdminSection = canManageUsers || canManageRoles || canViewAuditLogs || canViewAnalytics || canViewSapLogs || canManageMasterData || canViewSettings

  const showQuickActions = canDownloadRfp || canSubmitRfp || canDeclineRfp
  const { data: automationStatus } = useAutomationStatus()
  const setCollapsed = onCollapsedChange

  const isRunning = automationStatus?.status === 'Running'
  const progress = automationStatus?.progress || 0

  // Individual operation states for granular control
  const isDownloading = automationStatus?.download_running || false
  const isSubmitting = automationStatus?.submit_running || false
  const isDeclining = automationStatus?.decline_running || false

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'fixed left-0 top-0 z-40 h-screen transition-all duration-300 ease-in-out',
          collapsed ? 'w-[72px]' : 'w-[260px]'
        )}
        style={{
          background: 'linear-gradient(180deg, #1a1f24 0%, #32373c 100%)',
          borderRight: '1px solid rgba(6, 147, 227, 0.15)'
        }}
      >
        {/* Subtle gradient overlay */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'linear-gradient(180deg, rgba(6, 147, 227, 0.05) 0%, rgba(0, 208, 132, 0.03) 100%)'
          }}
        />

        <div className="flex h-full flex-col relative z-10">
          {/* Header */}
          <div
            className={cn('relative flex flex-col items-center px-3 pt-2 pb-3', collapsed && 'py-3')}
            style={{ borderBottom: '1px solid rgba(6, 147, 227, 0.2)' }}
          >
            {/* Toggle button - top right corner */}
            {!collapsed && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setCollapsed(true)}
                className="h-6 w-6 text-slate-400 hover:text-white absolute right-2 top-2 z-50 bg-slate-700 hover:bg-slate-600 rounded-full shadow-md"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
            )}
            <div className={cn('w-full flex flex-col items-center', collapsed && 'px-1')}>
              <div className={cn(
                'bg-white rounded-xl shadow-lg shadow-white/10 flex items-center justify-center',
                collapsed ? 'p-1.5 w-12 h-12' : 'p-[6px] w-full mt-4'
              )}>
                <img
                  src="/bahra-logo.svg"
                  alt="Bahra Electric"
                  className={cn('w-auto', collapsed ? 'h-8' : 'h-12 max-w-full')}
                />
              </div>
              {!collapsed && (
                <span className="text-base font-semibold text-white mt-2 text-center">RFP Portal</span>
              )}
            </div>
          </div>

          {/* Collapsed expand button */}
          {collapsed && (
            <div className="px-3 py-3" style={{ borderBottom: '1px solid rgba(6, 147, 227, 0.15)' }}>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setCollapsed(false)}
                className="w-full h-8 text-slate-400 hover:text-white"
                style={{ backgroundColor: 'transparent' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(6, 147, 227, 0.2)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}

          <ScrollArea className="flex-1">
            <div className="px-3 py-4">
              {/* Main Navigation */}
              <NavSection title="Menu" collapsed={collapsed}>
                {canViewDashboard && (
                  <NavItem
                    path="/dashboard"
                    icon={LayoutDashboard}
                    label="Dashboard"
                    active={location.pathname === '/dashboard'}
                    collapsed={collapsed}
                  />
                )}
                {canViewRfpInsights && (
                  <NavItem
                    path="/dashboard/rfp-insights"
                    icon={FileSearch}
                    label="RFP Insights"
                    active={location.pathname === '/dashboard/rfp-insights'}
                    collapsed={collapsed}
                  />
                )}
                {canViewMaterialInsights && (
                  <NavItem
                    path="/dashboard/material-insights"
                    icon={Package}
                    label="Material Insights"
                    active={location.pathname === '/dashboard/material-insights'}
                    collapsed={collapsed}
                  />
                )}
                {canViewLogs && (
                  <NavItem
                    path="/dashboard/logs"
                    icon={ScrollText}
                    label="Activity Logs"
                    active={location.pathname === '/dashboard/logs'}
                    collapsed={collapsed}
                  />
                )}
                {canViewOpenRfp && (
                  <NavItem
                    path="/dashboard/open-rfps"
                    icon={MailWarning}
                    label="Open RFP"
                    active={location.pathname === '/dashboard/open-rfps'}
                    collapsed={collapsed}
                  />
                )}
              </NavSection>

              {/* Admin Section */}
              {showAdminSection && (
                <NavSection title="Administration" collapsed={collapsed} className="mt-6">
                  {canManageUsers && (
                    <NavItem
                      path="/admin/users"
                      icon={Users}
                      label="Users"
                      active={location.pathname === '/admin/users'}
                      collapsed={collapsed}
                    />
                  )}
                  {canManageRoles && (
                    <NavItem
                      path="/admin/roles"
                      icon={Shield}
                      label="Roles"
                      active={location.pathname === '/admin/roles'}
                      collapsed={collapsed}
                    />
                  )}
                  {canViewAuditLogs && (
                    <NavItem
                      path="/admin/audit-logs"
                      icon={ScrollText}
                      label="Audit Logs"
                      active={location.pathname === '/admin/audit-logs'}
                      collapsed={collapsed}
                    />
                  )}
                  {canViewAnalytics && (
                    <NavItem
                      path="/dashboard/analytics"
                      icon={BarChart3}
                      label="Analytics"
                      active={location.pathname === '/dashboard/analytics'}
                      collapsed={collapsed}
                    />
                  )}
                  {canViewSapLogs && (
                    <NavItem
                      path="/admin/sap-logs"
                      icon={KeyRound}
                      label="SAP Logs"
                      active={location.pathname === '/admin/sap-logs'}
                      collapsed={collapsed}
                    />
                  )}
                  {canManageMasterData && (
                    <NavItem
                      path="/admin/master-data"
                      icon={Database}
                      label="Master Data"
                      active={location.pathname === '/admin/master-data'}
                      collapsed={collapsed}
                    />
                  )}
                  {canViewSettings && (
                    <NavItem
                      path="/admin/system-settings"
                      icon={SlidersHorizontal}
                      label="System Settings"
                      active={location.pathname === '/admin/system-settings'}
                      collapsed={collapsed}
                    />
                  )}
                </NavSection>
              )}

              {/* Quick Actions */}
              {showQuickActions && (
                <div className={cn('mt-6', collapsed ? 'px-0' : 'px-1')}>
                  {!collapsed && (
                    <div className="flex items-center gap-2 px-2 mb-3">
                      <Zap className="h-3.5 w-3.5" style={{ color: '#fcb900' }} />
                      <span className="text-xs font-medium uppercase tracking-wider" style={{ color: '#abb8c3' }}>
                        Quick Actions
                      </span>
                    </div>
                  )}
                  <div className="space-y-1.5">
                    {canDownloadRfp && (
                      <QuickAction
                        icon={Download}
                        label="Download RFPs"
                        onClick={onDownloadRfps}
                        collapsed={collapsed}
                        disabled={isDownloading}
                        variant="primary"
                      />
                    )}
                    {canSubmitRfp && (
                      <QuickAction
                        icon={Send}
                        label="Submit RFP"
                        onClick={onSubmitRfp}
                        collapsed={collapsed}
                        disabled={isSubmitting}
                        variant="success"
                      />
                    )}
                    {canDeclineRfp && (
                      <QuickAction
                        icon={Ban}
                        label="Decline RFP"
                        onClick={onDeclineRfp}
                        collapsed={collapsed}
                        disabled={isDeclining}
                        variant="danger"
                      />
                    )}
                  </div>
                </div>
              )}

              {/* Settings Section */}
              {(canSchedule || canChangeSapPassword) && (
                <div className={cn('mt-6', collapsed ? 'px-0' : 'px-1')}>
                  {!collapsed && (
                    <div className="flex items-center gap-2 px-2 mb-3">
                      <Settings className="h-3.5 w-3.5" style={{ color: '#abb8c3' }} />
                      <span className="text-xs font-medium uppercase tracking-wider" style={{ color: '#abb8c3' }}>
                        Settings
                      </span>
                    </div>
                  )}
                  <div className="space-y-1.5">
                    {canSchedule && (
                      <QuickAction
                        icon={Clock}
                        label="Schedule"
                        onClick={onSchedule}
                        collapsed={collapsed}
                        variant="ghost"
                      />
                    )}
                    {canChangeSapPassword && (
                      <QuickAction
                        icon={KeyRound}
                        label="SAP Password"
                        onClick={onChangeSapPassword}
                        collapsed={collapsed}
                        variant="ghost"
                      />
                    )}
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>

          {/* Status Footer */}
          <div
            className={cn('p-3', collapsed ? 'px-2' : 'px-4')}
            style={{ borderTop: '1px solid rgba(6, 147, 227, 0.2)' }}
          >
            {!collapsed ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Activity className={cn(
                      'h-4 w-4',
                      isRunning ? 'animate-pulse' : ''
                    )}
                    style={{ color: isRunning ? '#fcb900' : '#00d084' }}
                    />
                    <span className="text-sm font-medium" style={{ color: '#e2e8f0' }}>
                      {automationStatus?.status || 'Ready'}
                    </span>
                  </div>
                  {isRunning && (
                    <span className="text-xs" style={{ color: '#abb8c3' }}>{progress}%</span>
                  )}
                </div>
                {/* Detailed progress info */}
                {isRunning && automationStatus?.progress_details && (
                  <div className="space-y-1">
                    {isDownloading && automationStatus.progress_details.download && (
                      <div className="text-xs" style={{ color: '#abb8c3' }}>
                        <span className="font-medium" style={{ color: '#0693e3' }}>Download:</span>{' '}
                        {automationStatus.progress_details.download.current}/{automationStatus.progress_details.download.total}
                        {automationStatus.progress_details.download.current_item && (
                          <span className="block truncate max-w-[180px]" title={automationStatus.progress_details.download.current_item}>
                            {automationStatus.progress_details.download.current_item}
                          </span>
                        )}
                      </div>
                    )}
                    {isSubmitting && automationStatus.progress_details.submit && (
                      <div className="text-xs" style={{ color: '#abb8c3' }}>
                        <span className="font-medium" style={{ color: '#00d084' }}>Submit:</span>{' '}
                        {automationStatus.progress_details.submit.message || 'Processing...'}
                      </div>
                    )}
                    {isDeclining && automationStatus.progress_details.decline && (
                      <div className="text-xs" style={{ color: '#abb8c3' }}>
                        <span className="font-medium" style={{ color: '#ff6b6b' }}>Decline:</span>{' '}
                        {automationStatus.progress_details.decline.message || 'Processing...'}
                      </div>
                    )}
                  </div>
                )}
                {isRunning && (
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: '#32373c' }}>
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${progress}%`,
                        background: 'linear-gradient(90deg, #0693e3 0%, #00d084 100%)'
                      }}
                    />
                  </div>
                )}
              </div>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex justify-center">
                    <div
                      className={cn('w-3 h-3 rounded-full', isRunning && 'animate-pulse')}
                      style={{ backgroundColor: isRunning ? '#fcb900' : '#00d084' }}
                    />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="right">
                  <p>{automationStatus?.status || 'Ready'}</p>
                  {isDownloading && automationStatus?.progress_details?.download && (
                    <p className="text-xs">
                      Download: {automationStatus.progress_details.download.current}/{automationStatus.progress_details.download.total}
                    </p>
                  )}
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        </div>
      </aside>
    </TooltipProvider>
  )
}

interface NavSectionProps {
  title: string
  collapsed: boolean
  children: React.ReactNode
  className?: string
}

function NavSection({ title, collapsed, children, className }: NavSectionProps) {
  return (
    <div className={className}>
      {!collapsed && (
        <div className="px-2 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider" style={{ color: '#abb8c3' }}>
            {title}
          </span>
        </div>
      )}
      <nav className="space-y-1">{children}</nav>
    </div>
  )
}

interface NavItemProps {
  path: string
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>
  label: string
  active: boolean
  collapsed: boolean
}

function NavItem({ path, icon: Icon, label, active, collapsed }: NavItemProps) {
  const content = (
    <Link
      to={path}
      className={cn(
        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200',
        collapsed && 'justify-center px-2'
      )}
      style={{
        color: active ? '#ffffff' : '#abb8c3',
        backgroundColor: active ? 'rgba(6, 147, 227, 0.2)' : 'transparent',
        borderLeft: active ? '3px solid #0693e3' : '3px solid transparent',
      }}
      onMouseEnter={(e) => {
        if (!active) {
          e.currentTarget.style.backgroundColor = 'rgba(6, 147, 227, 0.1)'
          e.currentTarget.style.color = '#ffffff'
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          e.currentTarget.style.backgroundColor = 'transparent'
          e.currentTarget.style.color = '#abb8c3'
        }
      }}
    >
      <Icon
        className="h-[18px] w-[18px] shrink-0"
        style={{ color: active ? '#0693e3' : 'inherit' }}
      />
      {!collapsed && <span>{label}</span>}
    </Link>
  )

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{content}</TooltipTrigger>
        <TooltipContent side="right" className="font-medium">
          {label}
        </TooltipContent>
      </Tooltip>
    )
  }

  return content
}

interface QuickActionProps {
  icon: React.ComponentType<{ className?: string }>
  label: string
  onClick: () => void
  collapsed: boolean
  disabled?: boolean
  variant?: 'primary' | 'success' | 'danger' | 'ghost'
}

function QuickAction({
  icon: Icon,
  label,
  onClick,
  collapsed,
  disabled,
  variant = 'ghost',
}: QuickActionProps) {
  const variantStyles = {
    primary: {
      background: 'linear-gradient(135deg, #0693e3 0%, #0570b0 100%)',
      color: '#ffffff',
      boxShadow: '0 4px 15px rgba(6, 147, 227, 0.3)',
      border: 'none',
      hoverBg: 'linear-gradient(135deg, #00d084 0%, #00a868 100%)',
    },
    success: {
      background: 'linear-gradient(135deg, #00d084 0%, #00a868 100%)',
      color: '#ffffff',
      boxShadow: '0 4px 15px rgba(0, 208, 132, 0.3)',
      border: 'none',
      hoverBg: 'linear-gradient(135deg, #0693e3 0%, #0570b0 100%)',
    },
    danger: {
      background: 'rgba(207, 46, 46, 0.15)',
      color: '#ff6b6b',
      boxShadow: 'none',
      border: '1px solid rgba(207, 46, 46, 0.3)',
      hoverBg: 'rgba(207, 46, 46, 0.25)',
    },
    ghost: {
      background: 'rgba(50, 55, 60, 0.5)',
      color: '#e2e8f0',
      boxShadow: 'none',
      border: '1px solid rgba(171, 184, 195, 0.2)',
      hoverBg: 'rgba(6, 147, 227, 0.15)',
    },
  }

  const style = variantStyles[variant]

  const buttonContent = (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'w-full flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200',
        disabled && 'opacity-50 cursor-not-allowed',
        collapsed && 'justify-center px-2'
      )}
      style={{
        background: style.background,
        color: style.color,
        boxShadow: style.boxShadow,
        border: style.border,
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.background = style.hoverBg
          e.currentTarget.style.transform = 'translateY(-1px)'
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          e.currentTarget.style.background = style.background
          e.currentTarget.style.transform = 'translateY(0)'
        }
      }}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{label}</span>}
    </button>
  )

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{buttonContent}</TooltipTrigger>
        <TooltipContent side="right" className="font-medium">
          {label}
        </TooltipContent>
      </Tooltip>
    )
  }

  return buttonContent
}
