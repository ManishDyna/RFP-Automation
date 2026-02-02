import { useQuery } from '@tanstack/react-query'
import { KeyRound, Search } from 'lucide-react'
import { useState } from 'react'

import { PageWrapper } from '@/components/layout/page-wrapper'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
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

export default function SapPasswordLogsPage() {
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
                    <TableHead>Username</TableHead>
                    <TableHead>Changed By</TableHead>
                    <TableHead>Change Time</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Notes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredLogs.map((log: any, index: number) => (
                    <TableRow key={log.id || index}>
                      <TableCell className="font-medium">
                        {log.username || '-'}
                      </TableCell>
                      <TableCell>{log.changed_by || '-'}</TableCell>
                      <TableCell>{log.change_time || '-'}</TableCell>
                      <TableCell>
                        <Badge
                          variant={log.status === 'success' ? 'success' : 'destructive'}
                        >
                          {log.status || 'Unknown'}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate">
                        {log.notes || '-'}
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
