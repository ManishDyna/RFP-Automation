const API_BASE_URL = '/api'

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
  // Authentication
  login: async (email: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      credentials: 'include',
    })
    return handleResponse<{ redirect: string }>(response)
  },

  logout: async () => {
    const response = await fetch(`${API_BASE_URL}/logout`, {
      method: 'POST',
      credentials: 'include',
    })
    return handleResponse(response)
  },

  forgotPassword: async (email: string) => {
    const response = await fetch(`${API_BASE_URL}/forgot`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
    return handleResponse(response)
  },

  resetPassword: async (token: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, password }),
    })
    return handleResponse(response)
  },

  refreshSession: async () => {
    const response = await fetch(`${API_BASE_URL}/session/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
    return handleResponse(response)
  },

  getSessionStatus: async () => {
    const response = await fetch(`${API_BASE_URL}/session/status`, {
      credentials: 'include',
    })
    return handleResponse<{ valid: boolean; user?: any }>(response)
  },

  // Dashboard
  getDashboardData: async () => {
    const response = await fetch(`${API_BASE_URL}/dashboard/data`, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  // RFP Operations
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
    const response = await fetch(`${API_BASE_URL}/dashboard/rfp-details?${searchParams}`, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  // Automation
  getAutomationStatus: async () => {
    const response = await fetch(`${API_BASE_URL}/automation/status`, {
      credentials: 'include',
    })
    return handleResponse<{ status: string; progress: number }>(response)
  },

  downloadRfps: async (company?: string) => {
    const url = company
      ? `${API_BASE_URL}/download-rfp?company=${encodeURIComponent(company)}`
      : `${API_BASE_URL}/download-rfp`
    const response = await fetch(url, {
      credentials: 'include',
    })
    return handleResponse(response)
  },

  submitRfp: async (formData: FormData) => {
    const response = await fetch(`${API_BASE_URL}/dashboard/submit-rfp`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    })
    return handleResponse(response)
  },

  declineRfp: async (rfpTitle: string, company: string) => {
    const response = await fetch(`${API_BASE_URL}/decline-rfp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rfp_title: rfpTitle, company }),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  updateRfpStatus: async (rfpId: string, status: string) => {
    const response = await fetch(`${API_BASE_URL}/rfp/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rfp_id: rfpId, status }),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  syncPortalData: async () => {
    const response = await fetch(`${API_BASE_URL}/sync_portal_data`, {
      credentials: 'include',
    })
    return handleResponse(response)
  },

  // Logs
  getAutomationLogs: async (page: number = 1, pageSize: number = 20) => {
    const response = await fetch(
      `${API_BASE_URL}/dashboard/view-logs?page=${page}&page_size=${pageSize}`,
      { credentials: 'include' }
    )
    return handleResponse<any>(response)
  },

  // User Management
  getUsers: async () => {
    const response = await fetch(`${API_BASE_URL}/users/user-list`, {
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
    const response = await fetch(`${API_BASE_URL}/users/create`, {
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
    const response = await fetch(`${API_BASE_URL}/users/update/${userId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  deleteUser: async (userId: string) => {
    const response = await fetch(`${API_BASE_URL}/users/delete/${userId}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    return handleResponse(response)
  },

  // Profile
  getProfile: async () => {
    const response = await fetch(`${API_BASE_URL}/profile`, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  updateProfile: async (profileData: { name?: string; mobile?: string }) => {
    const response = await fetch(`${API_BASE_URL}/profile/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profileData),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  changePassword: async (currentPassword: string, newPassword: string) => {
    const response = await fetch(`${API_BASE_URL}/profile/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  // SAP Password
  changeSapPassword: async (username: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/sap/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      credentials: 'include',
    })
    return handleResponse(response)
  },

  getSapPasswordLogs: async () => {
    const response = await fetch(`${API_BASE_URL}/dashboard/sap-password-logs`, {
      credentials: 'include',
    })
    return handleResponse<any>(response)
  },

  // Schedule
  saveSchedule: async (scheduleData: any) => {
    const response = await fetch(`${API_BASE_URL}/schedule/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scheduleData),
      credentials: 'include',
    })
    return handleResponse(response)
  },
}
