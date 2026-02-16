import { ENDPOINTS } from './endpoints'

export interface ApiError {
  message: string
  status: number
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = 'Something went wrong. Please try again.'
    try {
      const data = await response.json()
      message = data.detail || data.message || message
    } catch {
      const text = await response.text().catch(() => '')
      if (text) message = text
    }
    const error: ApiError = {
      message,
      status: response.status,
    }
    throw error
  }

  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    return response.json()
  }
  return response.text() as unknown as T
}

export const api = {
  // ==================== Authentication ====================
  login: async (email: string, password: string) => {
    const response = await fetch(ENDPOINTS.AUTH.LOGIN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      credentials: 'include',
    })
    return handleResponse<{ redirect: string }>(response)
  },

  logout: async () => {
    const response = await fetch(ENDPOINTS.AUTH.LOGOUT, {
      method: 'POST',
      credentials: 'include',
    })
    return handleResponse(response)
  },

  forgotPassword: async (email: string) => {
    const response = await fetch(ENDPOINTS.AUTH.FORGOT_PASSWORD, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
    return handleResponse(response)
  },

  resetPassword: async (token: string, password: string) => {
    const response = await fetch(ENDPOINTS.AUTH.RESET_PASSWORD, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, password }),
    })
    return handleResponse(response)
  },

  refreshSession: async () => {
    const response = await fetch(ENDPOINTS.AUTH.SESSION_REFRESH, {
      method: 'POST',
      credentials: 'include',
    })
    return handleResponse(response)
  },

  getSessionStatus: async () => {
    const response = await fetch(ENDPOINTS.AUTH.SESSION_STATUS, {
      credentials: 'include',
    })
    return handleResponse<{ valid: boolean; user?: any }>(response)
  },

  // ==================== Dashboard ====================
  getDashboardData: async () => {
    const response = await fetch(ENDPOINTS.DASHBOARD.DATA, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  // ==================== RFP Operations ====================
  getRfpDetails: async (params: {
    status?: string
    company?: string
    start_date?: string
    end_date?: string
    search?: string
    material_match?: string
    keyword_match?: string
    participation?: string
    limit?: number
    offset?: number
  }) => {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') searchParams.append(key, String(value))
    })
    const response = await fetch(`${ENDPOINTS.DASHBOARD.RFP_DETAILS}?${searchParams}`, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  // ==================== Automation ====================
  getAutomationStatus: async () => {
    const response = await fetch(ENDPOINTS.AUTOMATION.STATUS, {
      credentials: 'include',
    })
    return handleResponse<{ status: string; progress: number }>(response)
  },

  downloadRfps: async (company?: string) => {
    const response = await fetch(ENDPOINTS.AUTOMATION.DOWNLOAD_ALL_RFPS, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company: company || '' }),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  downloadOpenRfps: async (company?: string) => {
    const params = new URLSearchParams()
    if (company) params.append('company', company)
    const url = params.toString()
      ? `${ENDPOINTS.RFP.DOWNLOAD}?${params}`
      : ENDPOINTS.RFP.DOWNLOAD
    const response = await fetch(url, {
      credentials: 'include',
    })
    return handleResponse(response)
  },

  validateRfp: async (rfpId: string) => {
    const response = await fetch(
      `${ENDPOINTS.DASHBOARD.VALIDATE_RFP}?rfp_id=${encodeURIComponent(rfpId)}`,
      { credentials: 'include' }
    )
    return handleResponse<{ ok: boolean; rfp_id: string; company: string; status: string }>(response)
  },

  submitRfp: async (formData: FormData) => {
    const response = await fetch(ENDPOINTS.DASHBOARD.SUBMIT_RFP, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    })
    return handleResponse(response)
  },

  declineRfp: async (rfpTitle: string, company: string) => {
    const response = await fetch(ENDPOINTS.RFP.DECLINE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rfp_title: rfpTitle, company }),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  updateRfpStatus: async (rfpId: string, status: string) => {
    const response = await fetch(ENDPOINTS.RFP.UPDATE_STATUS, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rfp_id: rfpId, status }),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  syncPortalData: async () => {
    const response = await fetch(ENDPOINTS.RFP.SYNC_PORTAL, {
      credentials: 'include',
    })
    return handleResponse(response)
  },

  downloadExcel: async (rfpId: string, company?: string) => {
    const url = company
      ? `${ENDPOINTS.DASHBOARD.VIEW_EXCEL(rfpId)}?company=${encodeURIComponent(company)}`
      : ENDPOINTS.DASHBOARD.VIEW_EXCEL(rfpId)
    const response = await fetch(url, { credentials: 'include' })
    if (!response.ok) {
      let message = 'Failed to download Excel file'
      try {
        const data = await response.json()
        message = data.detail || message
      } catch {}
      throw { message, status: response.status }
    }
    const blob = await response.blob()
    const disposition = response.headers.get('Content-Disposition')
    let filename = `${rfpId}.xls`
    if (disposition) {
      const match = disposition.match(/filename="?([^"]+)"?/)
      if (match) filename = match[1]
    }
    const downloadUrl = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(downloadUrl)
  },

  // ==================== RFP Match Percentages ====================
  getBatchMatchPercentages: async (rfpIds: string[]) => {
    const params = new URLSearchParams({ rfp_ids: rfpIds.join(',') })
    const response = await fetch(`${ENDPOINTS.RFP.BATCH_MATCH_PERCENTAGES}?${params}`, {
      credentials: 'include',
    })
    const data = await handleResponse<{ ok: boolean; results: Record<string, { match_percentage: number; total_materials: number; matched_count: number }> }>(response)
    return data.results
  },

  getRfpMaterials: async (rfpId: string) => {
    const response = await fetch(ENDPOINTS.RFP.GET_MATERIALS(rfpId), {
      credentials: 'include',
    })
    return handleResponse<{
      rfp_id: string
      total_materials: number
      matched_count: number
      match_percentage: number
      materials: Array<{
        material_code: string
        name: string
        description: string
        is_matched: boolean
        match_method: string | null
        master_description: string | null
      }>
    }>(response)
  },

  // ==================== Material Insights ====================
  getMaterialInsights: async (params: {
    rfp_id?: string
    company?: string
    material_match?: string
    keyword_match?: string
    participated?: string
    search?: string
    limit?: number
    offset?: number
  }) => {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') searchParams.append(key, String(value))
    })
    const response = await fetch(`${ENDPOINTS.DASHBOARD.MATERIAL_INSIGHTS}?${searchParams}`, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  getMaterialInsightsGrouped: async (params: {
    tab?: string
    company?: string
    search?: string
    participated?: string
    limit?: number
    offset?: number
    refresh?: number
  }) => {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') searchParams.append(key, String(value))
    })
    const response = await fetch(`${ENDPOINTS.DASHBOARD.MATERIAL_INSIGHTS_GROUPED}?${searchParams}`, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  // ==================== Logs ====================
  getAutomationLogs: async (page: number = 1, pageSize: number = 20) => {
    const response = await fetch(
      `${ENDPOINTS.DASHBOARD.VIEW_LOGS}?page=${page}&page_size=${pageSize}`,
      { credentials: 'include' }
    )
    return handleResponse<any>(response)
  },

  // ==================== Error Files ====================
  getErrorFiles: async (rfpId?: string) => {
    const params = rfpId ? `?rfp_id=${encodeURIComponent(rfpId)}` : ''
    const response = await fetch(`${ENDPOINTS.ERROR_FILES.LIST}${params}`, {
      credentials: 'include',
    })
    return handleResponse<{ files: Array<{ filename: string; size: number; modified: number; type: string }> }>(response)
  },

  getErrorFileContent: async (filename: string) => {
    const response = await fetch(ENDPOINTS.ERROR_FILES.CONTENT(filename), {
      credentials: 'include',
    })
    return handleResponse<{ filename: string; type: string; content: any }>(response)
  },

  // ==================== User Management ====================
  getUsers: async () => {
    const response = await fetch(ENDPOINTS.USERS.LIST, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  createUser: async (userData: {
    name: string
    email: string
    mobile: string
    role: string
    password: string
  }) => {
    // Map 'mobile' to 'mobile_number' for backend compatibility
    const payload = {
      name: userData.name,
      email: userData.email,
      mobile_number: userData.mobile,
      role: userData.role,
      password: userData.password,
    }
    const response = await fetch(ENDPOINTS.USERS.CREATE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  updateUser: async (userId: string, userData: any) => {
    // Map 'mobile' to 'mobile_number' for backend compatibility
    const payload = { ...userData }
    if ('mobile' in payload) {
      payload.mobile_number = payload.mobile
      delete payload.mobile
    }
    const response = await fetch(ENDPOINTS.USERS.UPDATE(userId), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  deleteUser: async (userId: string) => {
    const response = await fetch(ENDPOINTS.USERS.DELETE(userId), {
      method: 'DELETE',
      credentials: 'include',
    })
    return handleResponse(response)
  },

  // ==================== Profile ====================
  getProfile: async () => {
    const response = await fetch(ENDPOINTS.PROFILE.GET, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  updateProfile: async (profileData: { name?: string; mobile?: string }) => {
    const response = await fetch(ENDPOINTS.PROFILE.UPDATE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profileData),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  changePassword: async (currentPassword: string, newPassword: string) => {
    const response = await fetch(ENDPOINTS.PROFILE.CHANGE_PASSWORD, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  // ==================== SAP Password ====================
  changeSapPassword: async (username: string, password: string) => {
    const response = await fetch(ENDPOINTS.SAP.CHANGE_PASSWORD, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  getSapPasswordLogs: async () => {
    const response = await fetch(ENDPOINTS.DASHBOARD.SAP_PASSWORD_LOGS, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  // ==================== Schedule ====================
  getSchedule: async () => {
    const response = await fetch(ENDPOINTS.SCHEDULE.GET_LATEST, {
      credentials: 'include',
    })
    return handleResponse<{ ok: boolean; data: any }>(response)
  },

  saveSchedule: async (scheduleData: any) => {
    const response = await fetch(ENDPOINTS.SCHEDULE.SAVE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scheduleData),
      credentials: 'include',
    })
    return handleResponse(response)
  },
}
