import { ENDPOINTS } from './endpoints'

export interface ApiError {
  message: string
  status: number
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = {
      message: await response.text(),
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
  }) => {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value) searchParams.append(key, value)
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
    const url = company
      ? `${ENDPOINTS.RFP.DOWNLOAD}?company=${encodeURIComponent(company)}`
      : ENDPOINTS.RFP.DOWNLOAD
    const response = await fetch(url, {
      credentials: 'include',
    })
    return handleResponse(response)
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

  // ==================== Logs ====================
  getAutomationLogs: async (page: number = 1, pageSize: number = 20) => {
    const response = await fetch(
      `${ENDPOINTS.DASHBOARD.VIEW_LOGS}?page=${page}&page_size=${pageSize}`,
      { credentials: 'include' }
    )
    return handleResponse<any>(response)
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
