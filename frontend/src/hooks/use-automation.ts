import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export interface ProgressDetails {
  current: number
  total: number
  percentage: number
  current_item: string
  message: string
}

export interface AutomationStatus {
  status: 'Ready' | 'Running' | 'Completed' | 'Error'
  progress: number
  message?: string
  // Individual operation states for concurrent operations
  download_running: boolean
  submit_running: boolean
  decline_running: boolean
  sync_running: boolean
  submitting_rfps: string[]
  // Detailed progress for each operation
  progress_details: {
    download: ProgressDetails | null
    submit: ProgressDetails | null
    decline: ProgressDetails | null
    sync: ProgressDetails | null
  }
}

export function useAutomationStatus(enabled = true) {
  return useQuery({
    queryKey: ['automationStatus'],
    queryFn: async (): Promise<AutomationStatus> => {
      const result = await api.getAutomationStatus()
      return {
        status: result.status as AutomationStatus['status'],
        progress: result.progress || 0,
        // Include individual operation states for granular UI control
        download_running: result.download_running || false,
        submit_running: result.submit_running || false,
        decline_running: result.decline_running || false,
        sync_running: result.sync_running || false,
        submitting_rfps: result.submitting_rfps || [],
        // Include detailed progress
        progress_details: result.progress_details || {
          download: null,
          submit: null,
          decline: null,
          sync: null,
        },
      }
    },
    refetchInterval: (query) => {
      // Adaptive polling: more frequent when running, less when idle
      const data = query.state.data
      if (data?.status === 'Running') {
        return 3000 // Poll every 3 seconds when running (reduced from 2s to lower network load)
      }
      return 30000 // Poll every 30 seconds when idle
    },
    enabled,
    // Keep previous data while refetching to prevent UI flicker
    placeholderData: (previousData) => previousData,
  })
}
