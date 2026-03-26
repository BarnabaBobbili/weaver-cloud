export type SensitivityLevel = 'public' | 'internal' | 'confidential' | 'highly_sensitive';
export type UserRole = 'admin' | 'analyst' | 'viewer';
export type AuditSeverity = 'info' | 'warning' | 'critical';
export type ShareStatus = 'active' | 'expired' | 'revoked';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  mfa_enabled: boolean;
  failed_login_attempts: number;
  created_at: string;
  updated_at: string;
  last_login?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
}

export interface MFAVerifyRequest {
  totp_code: string;
  temp_token?: string;
}

export interface ExplanationFactor {
  feature: string;
  weight: number;
}

export interface PiiReason {
  pattern: string;
  label: string;
  match: string;
  line: number;
  col_start: number;
}

export interface SegmentResult {
  segment_id: number;
  source: string;
  line_start: number;
  line_end: number;
  content_preview: string;
  level: SensitivityLevel;
  level_int: number;
  has_pii: boolean;
  reasons: PiiReason[];
  explanation: string;
  page?: number;
}

export interface ClassificationResult {
  classification_id: string;
  level: SensitivityLevel;
  confidence: number;
  explanation_factors: ExplanationFactor[];
  explanation_summary: string;
  recommended_policy: CryptoPolicy;
  segments?: SegmentResult[];
  total_findings?: number;
  extracted_text?: string | null;
  guest?: boolean;
}

export interface GuestClassificationResult extends Omit<ClassificationResult, 'classification_id'> {
  classification_id?: string;
  guest: true;
}

export interface ClassificationRecord {
  id: string;
  input_text_preview: string;
  input_type: 'text' | 'file';
  file_name?: string;
  predicted_level: SensitivityLevel;
  confidence_score: number;
  explanation_summary: string;
  explanation_details?: ExplanationFactor[];
  policy_applied_id: string;
  policy?: CryptoPolicy;
  created_at: string;
}

export interface CryptoPolicy {
  id: string;
  sensitivity_level: SensitivityLevel;
  display_name: string;
  encryption_algo: string;
  key_derivation?: string;
  kdf_iterations?: number;
  signing_required: boolean;
  signing_algo?: string;
  hash_algo: string;
  require_mfa: boolean;
  description?: string;
}

export interface EncryptedPayload {
  id: string;
  classification_id: string;
  user_id: string;
  encryption_algo: string;
  original_size: number;
  encrypted_size: number;
  encryption_time_ms: number;
  created_at: string;
}

export interface EncryptResult {
  payload_id: string;
  encryption_algo: string;
  original_size: number;
  encrypted_size: number;
  encryption_time_ms: number;
  content_kind?: 'text' | 'file';
  file_name?: string | null;
  content_type?: string | null;
}

export interface DecryptResult {
  plaintext?: string | null;
  encryption_algo: string;
  integrity_verified: boolean;
  signature_verified?: boolean | null;
  content_kind?: 'text' | 'file';
  file_name?: string | null;
  content_type?: string | null;
  file_data_base64?: string | null;
}

export interface ShareLink {
  id: string;
  payload_id: string;
  token_prefix: string;
  share_url?: string | null;
  content_preview: string;
  file_name?: string | null;
  content_type?: string | null;
  expires_at?: string;
  max_access_count?: number;
  current_access_count: number;
  is_revoked: boolean;
  password_protected: boolean;
  created_at: string;
  status: ShareStatus;
  owner_email?: string;
}

export interface AuditLog {
  id: string;
  user_id?: string;
  user_email?: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  ip_address?: string;
  user_agent?: string;
  details?: Record<string, unknown>;
  severity: AuditSeverity;
  created_at: string;
}

export interface DashboardStats {
  total_classifications: number;
  total_encryptions: number;
  active_shares: number;
  total_users: number;
  classifications_this_week: number;
  encryptions_this_week: number;
  expiring_shares: number;
}

export interface ActivityEntry {
  id: string;
  action: string;
  details: string;
  level?: SensitivityLevel;
  user: string;
  created_at: string;
}

export interface AnalyticsOverview extends DashboardStats {
  classifications_this_month: number;
  avg_confidence: number | null;
  most_common_level: SensitivityLevel | null;
  most_common_pct: number;
}

export interface TimeSeriesPoint {
  date: string;
  public: number;
  internal: number;
  confidential: number;
  highly_sensitive: number;
}

export interface SensitivityDistribution {
  public: number;
  internal: number;
  confidential: number;
  highly_sensitive: number;
}

export interface AlgorithmUsage {
  algorithm: string;
  count: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
}

export interface BenchmarkResult {
  algorithm: string;
  operation: string;
  data_size: string;
  time_ms: number;
  throughput_mbs?: number;
  category: 'Symmetric' | 'Asymmetric' | 'KDF' | 'Hash';
}

export interface ProfileStats {
  total_classifications: number;
  total_encryptions: number;
  total_shares: number;
  active_shares: number;
}

export interface ProfileActivityItem {
  id: string;
  action: string;
  details: string;
  created_at: string;
}

export interface Session {
  id: string;
  device: string;
  browser: string;
  ip_address: string;
  last_active: string;
  is_current: boolean;
}

export interface ShareCreateResponse {
  share_id: string;
  token: string;
  share_url: string;
  token_prefix: string;
  expires_at?: string;
  max_access_count?: number;
}

export interface GuestShareCreateResponse {
  share_id: string;
  token: string;
  share_url: string;
  expires_at: string;
  max_access_count: number;
}

export interface MFASetupResponse {
  secret: string;
  provisioning_uri: string;
  qr_data: string;
}

export interface RecoveryCodesResponse {
  codes: string[];
}

export interface ShareAccessLog {
  id: string;
  accessed_at: string;
  ip_address?: string;
  user_agent?: string;
}

export interface NotificationItem {
  id: string;
  type: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationsResponse {
  items: NotificationItem[];
  unread: number;
}

export interface AdminHealth {
  db_records: Record<string, number>;
  uptime?: string;
  uptime_seconds?: number;
  uptime_human?: string;
  memory?: string;
  memory_mb?: number | null;
}

export interface AdminUserSummary {
  registrations_last_30_days?: number;
  new_registrations?: number;
  new_registrations_30d?: number;
  locked_accounts: number;
  mfa_adoption_pct: number;
  total_users: number;
}

export interface AdminSecurityAlerts {
  failed_logins_24h: number;
  locked_accounts: number;
  expiring_shares?: number;
  expiring_shares_24h?: number;
}

export interface ComplianceReport {
  total_encryptions: number;
  encryptions_by_level: Record<string, number>;
  unencrypted_ops: number;
  mfa_adoption_pct: number;
  locked_accounts: number;
  policy_violations: number;
  security_score: number;
}

export interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
}
