import { cn } from '@/lib/utils'

interface PageWrapperProps {
  children: React.ReactNode
  title?: string
  description?: string
  actions?: React.ReactNode
  className?: string
  noPadding?: boolean
}

export function PageWrapper({
  children,
  title,
  description,
  actions,
  className,
  noPadding = false,
}: PageWrapperProps) {
  return (
    <div className={cn('page-enter', className)}>
      {(title || description || actions) && (
        <div className={cn(
          'mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between',
          noPadding && 'px-0'
        )}>
          <div className="space-y-1">
            {title && (
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
                {title}
              </h1>
            )}
            {description && (
              <p className="text-sm text-slate-500 max-w-2xl">
                {description}
              </p>
            )}
          </div>
          {actions && (
            <div className="flex items-center gap-3 shrink-0">
              {actions}
            </div>
          )}
        </div>
      )}
      {children}
    </div>
  )
}
