import client from './client';
import type {
  AlgorithmUsage,
  AdminHealth,
  AdminSecurityAlerts,
  AdminUserSummary,
  AuditLog,
  AuthTokens,
  ClassificationResult,
  BenchmarkResult,
  ClassificationRecord,
  ComplianceReport,
  CryptoPolicy,
  DecryptResult,
  EncryptResult,
  GuestClassificationResult,
  GuestShareCreateResponse,
  LoginRequest,
  MFASetupResponse,
  NotificationsResponse,
  PaginatedResponse,
  ProfileActivityItem,
  ProfileStats,
  RecoveryCodesResponse,
  RegisterRequest,
  Session,
  ShareAccessLog,
  SensitivityDistribution,
  ShareLink,
  ShareCreateResponse,
  TimeSeriesPoint,
  User,
  AnalyticsOverview,
} from '../types';

export const authApi = {
  login: (data: LoginRequest) =>
    client.post<AuthTokens>('/api/auth/login', data),

  loginMfa: (data: { totp_code: string; temp_token: string }) =>
    client.post<AuthTokens>('/api/auth/login/mfa', data),

  register: (data: RegisterRequest) =>
    client.post<AuthTokens>('/api/auth/register', data),

  logout: () =>
    client.post('/api/auth/logout'),

  me: () =>
    client.get<User>('/api/auth/me'),

  mfaSetup: () =>
    client.post<MFASetupResponse>('/api/auth/mfa/setup'),

  mfaVerify: (totp_code: string) =>
    client.post('/api/auth/mfa/verify', { totp_code }),

  mfaDisable: (totp_code: string) =>
    client.post('/api/auth/mfa/disable', { totp_code }),

  recoveryCodes: () =>
    client.post<RecoveryCodesResponse>('/api/auth/mfa/recovery-codes'),

  loginRecovery: (data: { email: string; recovery_code: string }) =>
    client.post<AuthTokens>('/api/auth/login/recovery', data),
};

export const guestApi = {
  classifyText: (text: string) =>
    client.post<GuestClassificationResult>('/api/guest/classify/text', { text }),

  classifyFile: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return client.post<GuestClassificationResult>('/api/guest/classify/file', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  encrypt: (data: { plaintext: string; policy_level: string }) =>
    client.post<EncryptResult>('/api/guest/encrypt', data),

  share: (data: { payload_id: string; expires_hours: number; max_access: number; password?: string }) =>
    client.post<GuestShareCreateResponse>('/api/guest/share', data),
};

export const classifyApi = {
  classifyText: (text: string) =>
    client.post<ClassificationResult>('/api/classify/text', { text }),

  classifyFile: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return client.post<ClassificationResult>('/api/classify/file', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  history: (params: Record<string, string | number | undefined>) =>
    client.get<PaginatedResponse<ClassificationRecord>>('/api/classify/history', { params }),

  getById: (id: string) =>
    client.get(`/api/classify/${id}`),
};

export const encryptApi = {
  encrypt: (data: { classification_id: string; plaintext: string; password?: string; policy_override_level?: string }) =>
    client.post<EncryptResult>('/api/encrypt', data),

  encryptFile: (data: { classification_id: string; file: File; password?: string; policy_override_level?: string }) => {
    const form = new FormData();
    form.append('classification_id', data.classification_id);
    form.append('file', data.file);
    if (data.password) form.append('password', data.password);
    if (data.policy_override_level) form.append('policy_override_level', data.policy_override_level);
    return client.post<EncryptResult>('/api/encrypt/file', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  encryptDirect: (data: { plaintext: string; policy_level: string; password?: string }) =>
    client.post<EncryptResult>('/api/encrypt/direct', data),

  verifyMfa: (data: { classification_id: string; plaintext: string; password?: string; policy_override_level?: string; totp_code: string }) =>
    client.post<EncryptResult>('/api/encrypt/verify-mfa', data),

  verifyMfaFile: (data: { classification_id: string; file: File; password?: string; policy_override_level?: string; totp_code: string }) => {
    const form = new FormData();
    form.append('classification_id', data.classification_id);
    form.append('file', data.file);
    form.append('totp_code', data.totp_code);
    if (data.password) form.append('password', data.password);
    if (data.policy_override_level) form.append('policy_override_level', data.policy_override_level);
    return client.post<EncryptResult>('/api/encrypt/file/verify-mfa', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  reEncrypt: (payloadId: string, data: { policy_level: string; current_password?: string; new_password?: string }) =>
    client.post<EncryptResult>(`/api/encrypt/re-encrypt/${payloadId}`, data),
};

export const decryptApi = {
  decryptOwn: (payload_id: string, password?: string) =>
    client.post<DecryptResult>(`/api/decrypt/${payload_id}`, { password }),

  decryptShare: (token: string, password?: string) =>
    client.post<DecryptResult>(`/api/decrypt/share/${token}`, { password }),
};

export const shareApi = {
  create: (data: { payload_id: string; password?: string; expires_in?: string; max_access?: number }) =>
    client.post<ShareCreateResponse>('/api/share', data),

  mine: (page = 1) =>
    client.get<PaginatedResponse<ShareLink>>(`/api/share/mine?page=${page}`),

  stats: (link_id: string) =>
    client.get<ShareLink>(`/api/share/${link_id}/stats`),

  accessLogs: (link_id: string) =>
    client.get<{ items: ShareAccessLog[] }>(`/api/share/${link_id}/access-logs`),

  revoke: (link_id: string) =>
    client.delete(`/api/share/${link_id}`),
};

export const analyticsApi = {
  overview: () =>
    client.get<AnalyticsOverview>('/api/analytics/overview'),

  sensitivityDistribution: (range = '30D') =>
    client.get<SensitivityDistribution>(`/api/analytics/sensitivity-distribution?range=${range}`),

  sensitivityTimeseries: (range = '30D') =>
    client.get<{ items: TimeSeriesPoint[] }>(
      `/api/analytics/sensitivity-timeseries?range=${range}`
    ),

  algorithmUsage: () =>
    client.get<AlgorithmUsage[]>('/api/analytics/algorithm-usage'),

  auditLogs: (params?: Record<string, string | number>) =>
    client.get<PaginatedResponse<AuditLog>>('/api/analytics/audit-logs', { params }),

  adminHealth: () =>
    client.get<AdminHealth>('/api/analytics/admin/health'),

  adminUserSummary: () =>
    client.get<AdminUserSummary>('/api/analytics/admin/user-summary'),

  adminSecurityAlerts: () =>
    client.get<AdminSecurityAlerts>('/api/analytics/admin/security-alerts'),

  // Unified dashboard endpoint - automatically returns role-based data
  dashboard: () =>
    client.get<{
      total_classifications: number;
      classifications_this_week: number;
      total_encryptions: number;
      encryptions_this_week: number;
      total_users?: number; // Only present for admin users
      active_shares: number;
      sensitivity_distribution: {
        public: number;
        internal: number;
        confidential: number;
        highly_sensitive: number;
      };
      daily_activity: Array<{
        date: string;
        day: string;
        classifications: number;
        encryptions: number;
      }>;
      ml_model_source?: string; // Only present for admin users
    }>('/api/analytics'),

  triggerSynapseExport: () =>
    client.post<{ status: string; message: string; details?: unknown }>('/api/analytics/synapse/export'),
};

export const adminApi = {
  listUsers: (page = 1) =>
    client.get<PaginatedResponse<User>>(`/api/admin/users?page=${page}`),

  createUser: (data: { email: string; password: string; full_name: string; role: string }) =>
    client.post('/api/admin/users', data),

  updateUser: (id: string, data: Partial<{ role: string; is_active: boolean }>) =>
    client.put(`/api/admin/users/${id}`, data),

  deleteUser: (id: string) =>
    client.delete(`/api/admin/users/${id}`),

  resetMfa: (id: string) =>
    client.post(`/api/admin/users/${id}/reset-mfa`),

  unlockUser: (id: string) =>
    client.post(`/api/admin/users/${id}/unlock`),

  forceLogout: (id: string) =>
    client.post(`/api/admin/users/${id}/force-logout`),

  shares: (page = 1, search = '') =>
    client.get<PaginatedResponse<ShareLink>>('/api/admin/shares', { params: { page, search } }),

  revokeShare: (id: string) =>
    client.delete(`/api/admin/shares/${id}`),

  shareAccessLogs: (id: string) =>
    client.get<{ items: ShareAccessLog[] }>(`/api/admin/shares/${id}/access-logs`),

  adminAuditLogs: (params?: Record<string, string | number>) =>
    client.get<PaginatedResponse<AuditLog>>('/api/admin/audit-logs', { params }),

  exportAuditLogs: () =>
    client.get('/api/admin/audit-logs/export', { responseType: 'blob' }),

  complianceReport: () =>
    client.get<ComplianceReport>('/api/admin/compliance-report'),
};

export const policiesApi = {
  list: () =>
    client.get<CryptoPolicy[]>(`/api/policies`),

  getByLevel: (level: string) =>
    client.get<CryptoPolicy>(`/api/policies/${level}`),

  update: (id: string, data: Record<string, unknown>) =>
    client.put(`/api/policies/${id}`, data),
};

export const benchmarkApi = {
  run: () =>
    client.post<{ results: BenchmarkResult[] }>('/api/benchmarks/run'),

  results: () =>
    client.get<{ results: BenchmarkResult[]; message?: string }>('/api/benchmarks/results'),
};

export const profileApi = {
  get: () =>
    client.get<User>('/api/profile'),

  update: (data: { full_name?: string; email?: string }) =>
    client.put('/api/profile', data),

  changePassword: (data: { current_password: string; new_password: string }) =>
    client.put('/api/profile/password', data),

  activity: (page = 1) =>
    client.get<PaginatedResponse<ProfileActivityItem>>(`/api/profile/activity?page=${page}`),

  sessions: () =>
    client.get<Session[]>('/api/profile/sessions'),

  revokeSession: (id: string) =>
    client.delete(`/api/profile/sessions/${id}`),

  stats: () =>
    client.get<ProfileStats>('/api/profile/stats'),

  exportData: () =>
    client.get('/api/profile/export'),

  deleteAccount: () =>
    client.delete('/api/profile/account'),
};

export const notificationsApi = {
  list: () =>
    client.get<NotificationsResponse>('/api/notifications'),

  markRead: (id: string) =>
    client.post(`/api/notifications/${id}/read`),

  markAllRead: () =>
    client.post('/api/notifications/read-all'),
};
