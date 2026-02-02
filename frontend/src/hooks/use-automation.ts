import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export interface AutomationStatus {
  status: 'Ready' | 'Running' | 'Completed' | 'Error'
  progress: number
  message?: string
}

export function useAutomationStatus(enabled = true) {
  return useQuery({
    queryKey: ['automationStatus'],
    queryFn: async (): Promise<AutomationStatus> => {
      const result = await api.getAutomationStatus()
      return {
        status: result.status as AutomationStatus['status'],
        progress: result.progress || 0,
      }
    },
    refetchInterval: (query) => {
      // Poll more frequently when automation is running
      const data = query.state.data
      if (data?.status === 'Running') {
        return 2000 // Poll every 2 seconds when running
      }
      return 30000 // Poll every 30 seconds otherwise
    },
    enabled,
  })
}
