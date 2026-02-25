import { useQuery } from '@tanstack/react-query'
import { KeyRound, Search, CheckCircle, Calendar, User, Eye, EyeOff, Copy } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { useHasPermission } from '@/hooks/use-auth'

// Format date string to readable format
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '-'
  try {
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return '-'
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return '-'
  }
}

// Password cell component with show/hide toggle
function PasswordCell({ password }: { password: string | null | undefined }) {
  const [visible, setVisible] = useState(false)

  if (!password) return <span className="text-muted-foreground">-</span>

  const copyToClipboard = () => {
    navigator.clipboard.writeText(password)
    toast.success('Password copied to clipboard')
  }

  return (
    <div className="flex items-center gap-2">
      <code className="bg-slate-100 px-2 py-1 rounded text-sm font-mono min-w-[100px]">
        {visible ? password : '••••••••'}
      </code>
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={() => setVisible(!visible)}
        title={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={copyToClipboard}
        title="Copy password"
      >
        <Copy className="h-4 w-4" />
      </Button>
    </div>
  )
}

export default function SapPasswordLogsPage() {
  const hasPermission = useHasPermission('sap_password.view')
  const [searchTerm, setSearchTerm] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['sapPasswordLogs'],
    queryFn: api.getSapPasswordLogs,
  })

  const logs = data?.logs || []
  const filteredLogs = searchTerm
    ? logs.filter((log: any) =>
        Object.values(log).some((value) =>
          String(value).toLowerCase().includes(searchTerm.toLowerCase())
        )
      )
    : logs

  if (!hasPermission) return null

  return (
    <PageWrapper
      title="SAP Password Change Logs"
      description="View history of SAP password changes"
    >
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <KeyRound className="h-5 w-5" />
            Password Change History
          </CardTitle>
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search logs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <KeyRound className="h-12 w-12 mb-4 opacity-50" />
              <p>No password change logs found</p>
            </div>
          ) : (
            <ScrollArea className="h-[500px]">
              <Table>
                <TableHeader className="sticky top-0 bg-background z-10">
                  <TableRow>
                    <TableHead>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4" />
                        Username
                      </div>
                    </TableHead>
                    <TableHead>
                      <div className="flex items-center gap-2">
                        <KeyRound className="h-4 w-4" />
                        Password
                      </div>
                    </TableHead>
                    <TableHead>Changed By</TableHead>
                    <TableHead>
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4" />
                        Created
                      </div>
                    </TableHead>
                    <TableHead className="text-center">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLogs.map((log: any, index: number) => (
                    <TableRow key={log.id || index}>
                      <TableCell className="font-medium">
                        {log.username || '-'}
                      </TableCell>
                      <TableCell>
                        <PasswordCell password={log.password} />
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {log.created_by || log.updated_by || '-'}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(log.created)}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="success" className="gap-1">
                          <CheckCircle className="h-3 w-3" />
                          Saved
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </PageWrapper>
  )
}
