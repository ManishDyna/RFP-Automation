import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Download,
  RefreshCw,
  Bell,
  User,
  LogOut,
  Settings,
  ChevronDown,
  Search,
  Command,
  HelpCircle,
  Keyboard,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuShortcut,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from '@/components/ui/tooltip'
import { useAuth } from '@/hooks/use-auth'
import { cn } from '@/lib/utils'

interface HeaderProps {
  onDownloadAll: () => void
  onRefresh: () => void
}

export function Header({ onDownloadAll, onRefresh }: HeaderProps) {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [searchFocused, setSearchFocused] = useState(false)

  const initials = user?.name
    ? user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : 'U'

  const handleRefresh = async () => {
    setIsRefreshing(true)
    onRefresh()
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <TooltipProvider delayDuration={0}>
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/80 backdrop-blur-md px-6">
        {/* Left - Logo (hidden on desktop since sidebar has it) */}
        <div className="flex items-center gap-4 lg:hidden">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <span className="text-white font-bold text-sm">R</span>
            </div>
          </Link>
        </div>

        {/* Center - Search */}
        <div className="flex-1 max-w-xl mx-4 hidden md:block">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search RFPs, companies, logs..."
              className={cn(
                'pl-9 pr-20 h-9 bg-slate-50 border-slate-200',
                'focus:bg-white focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100',
                'placeholder:text-slate-400 text-sm transition-all',
                searchFocused && 'w-full'
              )}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
            />
            <div className="absolute right-2 top-1/2 -translate-y-1/2 hidden sm:flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 text-[10px] font-medium text-slate-400 bg-slate-100 border border-slate-200 rounded">
                <Command className="h-2.5 w-2.5 inline" />
              </kbd>
              <kbd className="px-1.5 py-0.5 text-[10px] font-medium text-slate-400 bg-slate-100 border border-slate-200 rounded">
                K
              </kbd>
            </div>
          </div>
        </div>

        {/* Right - Actions */}
        <div className="flex items-center gap-2">
          {/* Refresh Button */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleRefresh}
                className="h-9 w-9 text-slate-500 hover:text-slate-700 hover:bg-slate-100"
              >
                <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Refresh data</TooltipContent>
          </Tooltip>

          {/* Download Button */}
          <Button
            size="sm"
            onClick={onDownloadAll}
            className="h-9 bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm hidden sm:flex"
          >
            <Download className="h-4 w-4 mr-2" />
            Download RFPs
          </Button>

          {/* Mobile Download */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon"
                onClick={onDownloadAll}
                className="h-9 w-9 bg-indigo-600 hover:bg-indigo-700 text-white sm:hidden"
              >
                <Download className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Download RFPs</TooltipContent>
          </Tooltip>

          {/* Divider */}
          <div className="h-6 w-px bg-slate-200 mx-1 hidden sm:block" />

          {/* Notifications */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 text-slate-500 hover:text-slate-700 hover:bg-slate-100 relative"
              >
                <Bell className="h-4 w-4" />
                {/* Notification badge - uncomment when needed */}
                {/* <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-rose-500 ring-2 ring-white" /> */}
              </Button>
            </TooltipTrigger>
            <TooltipContent>Notifications</TooltipContent>
          </Tooltip>

          {/* Help */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 text-slate-500 hover:text-slate-700 hover:bg-slate-100 hidden lg:flex"
              >
                <HelpCircle className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Help & Support</TooltipContent>
          </Tooltip>

          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="h-9 flex items-center gap-2 px-2 hover:bg-slate-100"
              >
                <Avatar className="h-7 w-7">
                  <AvatarFallback className="bg-gradient-to-br from-indigo-500 to-violet-600 text-white text-xs font-medium">
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <div className="hidden lg:flex flex-col items-start">
                  <span className="text-sm font-medium text-slate-700 leading-none">
                    {user?.name || 'User'}
                  </span>
                </div>
                <ChevronDown className="h-3.5 w-3.5 text-slate-400 hidden lg:block" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-sm font-medium text-slate-900">{user?.name}</p>
                  <p className="text-xs text-slate-500">{user?.email}</p>
                  <span className="inline-flex items-center rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 ring-1 ring-inset ring-indigo-700/10 w-fit mt-1">
                    {user?.role || 'User'}
                  </span>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/dashboard/profile" className="flex items-center cursor-pointer">
                  <User className="mr-2 h-4 w-4 text-slate-500" />
                  <span>Profile</span>
                  <DropdownMenuShortcut>⇧⌘P</DropdownMenuShortcut>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/dashboard/profile" className="flex items-center cursor-pointer">
                  <Settings className="mr-2 h-4 w-4 text-slate-500" />
                  <span>Settings</span>
                  <DropdownMenuShortcut>⌘,</DropdownMenuShortcut>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem className="hidden lg:flex cursor-pointer">
                <Keyboard className="mr-2 h-4 w-4 text-slate-500" />
                <span>Keyboard shortcuts</span>
                <DropdownMenuShortcut>⌘K</DropdownMenuShortcut>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={handleLogout}
                className="text-rose-600 focus:text-rose-600 focus:bg-rose-50 cursor-pointer"
              >
                <LogOut className="mr-2 h-4 w-4" />
                <span>Log out</span>
                <DropdownMenuShortcut>⇧⌘Q</DropdownMenuShortcut>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
    </TooltipProvider>
  )
}
