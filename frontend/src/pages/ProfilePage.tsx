import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Laptop, Smartphone } from 'lucide-react';

import { authApi, profileApi } from '../api';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';
import type { ProfileActivityItem, ProfileStats, Session, User } from '../types';
import { getApiErrorMessage } from '../utils/apiError';
import { formatDate, formatDetails, formatRelativeTime, humanizeAction } from '../utils/formatters';

function PwStrength({ pw }: { pw: string }) {
  const score = !pw ? 0 : pw.length < 6 ? 1 : pw.length < 8 ? 2 : /[A-Z]/.test(pw) && /\d/.test(pw) && /[^A-Za-z0-9]/.test(pw) ? 4 : 3;
  const labels = ['', 'Weak', 'Fair', 'Strong', 'Excellent'];
  const colors = ['', 'var(--accent-red)', 'var(--accent-amber)', 'var(--accent-green)', 'var(--accent-blue)'];
  return (
    <div style={{ marginTop: 6 }}>
      <div className="pw-strength-bar">
        <div className="pw-strength-fill" style={{ width: `${score * 25}%`, background: colors[score] }} />
      </div>
      {score > 0 && <div style={{ fontSize: 11, color: colors[score], marginTop: 3 }}>{labels[score]}</div>}
    </div>
  );
}

const EMPTY_STATS: ProfileStats = {
  total_classifications: 0,
  total_encryptions: 0,
  total_shares: 0,
  active_shares: 0,
};

function isMobileSession(session: Session): boolean {
  const descriptor = `${session.device} ${session.browser}`.toLowerCase();
  return descriptor.includes('android') || descriptor.includes('iphone') || descriptor.includes('mobile');
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState<User | null>(user);
  const [stats, setStats] = useState<ProfileStats>(EMPTY_STATS);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activity, setActivity] = useState<ProfileActivityItem[]>([]);
  const [showEditForm, setShowEditForm] = useState(false);
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [showPwForm, setShowPwForm] = useState(false);
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [disableMfaCode, setDisableMfaCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [disablingMfa, setDisablingMfa] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const [profileResponse, statsResponse, sessionsResponse, activityResponse] = await Promise.all([
          profileApi.get(),
          profileApi.stats(),
          profileApi.sessions(),
          profileApi.activity(1),
        ]);

        if (cancelled) {
          return;
        }

        setProfile(profileResponse.data);
        setFullName(profileResponse.data.full_name);
        setStats(statsResponse.data);
        setSessions(sessionsResponse.data);
        setActivity(activityResponse.data.items);
      } catch (err) {
        if (!cancelled) {
          setError(getApiErrorMessage(err, 'Profile data is unavailable.'));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const initials = (profile?.full_name || user?.full_name || 'User')
    .split(' ')
    .map((part) => part[0] || '')
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const handleSaveProfile = async () => {
    if (!fullName.trim()) {
      setError('Full name cannot be empty.');
      return;
    }

    setSavingProfile(true);
    setError('');
    setSuccess('');
    try {
      await profileApi.update({ full_name: fullName.trim() });
      const refreshed = await profileApi.get();
      setProfile(refreshed.data);
      setFullName(refreshed.data.full_name);
      setShowEditForm(false);
      setSuccess('Profile updated.');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not update the profile.'));
    } finally {
      setSavingProfile(false);
    }
  };

  const handlePasswordChange = async () => {
    if (!currentPw || !newPw) {
      setError('Both current and new passwords are required.');
      return;
    }
    if (newPw !== confirmPw) {
      setError('New passwords do not match.');
      return;
    }

    setSavingPassword(true);
    setError('');
    setSuccess('');
    try {
      await profileApi.changePassword({ current_password: currentPw, new_password: newPw });
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
      setShowPwForm(false);
      setSuccess('Password updated.');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not update the password.'));
    } finally {
      setSavingPassword(false);
    }
  };

  const handleDisableMfa = async () => {
    if (!disableMfaCode.trim()) {
      setError('Enter your current TOTP code to disable MFA.');
      return;
    }

    setDisablingMfa(true);
    setError('');
    setSuccess('');
    try {
      await authApi.mfaDisable(disableMfaCode.trim());
      const refreshed = await profileApi.get();
      setProfile(refreshed.data);
      setDisableMfaCode('');
      setSuccess('MFA disabled.');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not disable MFA.'));
    } finally {
      setDisablingMfa(false);
    }
  };

  const handleRevokeSession = async (sessionId: string) => {
    setActionId(sessionId);
    setError('');
    setSuccess('');
    try {
      await profileApi.revokeSession(sessionId);
      setSessions((current) => current.filter((session) => session.id !== sessionId));
      setSuccess('Session revoked.');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not revoke the session.'));
    } finally {
      setActionId(null);
    }
  };

  const handleExportData = async () => {
    setExporting(true);
    setError('');
    setSuccess('');
    try {
      const response = await client.get('/api/profile/export', { responseType: 'blob' });
      downloadBlob('weaver-profile-export.json', response.data as Blob);
      setSuccess('Profile export downloaded.');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not export your account data.'));
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!window.confirm('Delete this account and queue data removal? This action cannot be undone.')) {
      return;
    }

    setDeleting(true);
    setError('');
    setSuccess('');
    try {
      await client.delete('/api/profile/account');
      logout();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not delete the account.'));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div style={{ maxWidth: 780, display: 'flex', flexDirection: 'column', gap: 24 }}>
      {(error || success) && (
        <div style={{
          padding: '10px 14px',
          background: error ? 'rgba(181,74,74,0.1)' : 'rgba(91,138,114,0.12)',
          border: `1px solid ${error ? 'var(--accent-red)' : 'var(--accent-green)'}`,
          borderRadius: 2,
          fontSize: 13,
          color: error ? 'var(--accent-red)' : 'var(--accent-green)',
        }}>
          {error || success}
        </div>
      )}

      <div className="card" style={{ padding: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'var(--accent-blue)', color: 'var(--bg-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 500, flexShrink: 0 }}>
            {initials}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 22, fontWeight: 500, color: 'var(--text-primary)' }}>{profile?.full_name || user?.full_name || 'User'}</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>{profile?.email || user?.email || '—'}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
              <span className="badge" style={{ color: 'var(--accent-red)', borderColor: 'var(--accent-red)', fontSize: 11 }}>
                {profile?.role || user?.role || 'viewer'}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Member since {formatDate(profile?.created_at || user?.created_at)}
              </span>
            </div>
          </div>
          <button className="link-blue" onClick={() => setShowEditForm((value) => !value)}>
            {showEditForm ? 'Close' : 'Edit Profile'}
          </button>
        </div>

        {showEditForm && (
          <div style={{ marginTop: 20, display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 1, minWidth: 220 }}>
              <label className="form-label">FULL NAME</label>
              <input className="form-input" value={fullName} onChange={(event) => setFullName(event.target.value)} />
            </div>
            <button className="btn btn-primary btn-sm" style={{ width: 150 }} onClick={handleSaveProfile} disabled={savingProfile}>
              {savingProfile ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        )}

        <div className="grid-4" style={{ marginTop: 24, gap: 12 }}>
          {[
            { label: 'CLASSIFICATIONS', value: stats.total_classifications, color: 'var(--text-primary)' },
            { label: 'ENCRYPTIONS', value: stats.total_encryptions, color: 'var(--text-primary)' },
            { label: 'SHARES CREATED', value: stats.total_shares, color: 'var(--text-primary)' },
            { label: 'ACTIVE SHARES', value: stats.active_shares, color: 'var(--accent-green)' },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 2, padding: 14 }}>
              <div style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-muted)' }}>{label}</div>
              <div style={{ fontSize: 20, fontWeight: 500, color, marginTop: 6 }}>{loading ? '—' : value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ padding: 24 }}>
        <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 16 }}>Security</div>

        <div className="row-between" style={{ borderBottom: '1px solid var(--border-subtle)', padding: '16px 0', gap: 16 }}>
          <div>
            <div style={{ fontSize: 14, color: 'var(--text-primary)' }}>Two-Factor Authentication</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              {profile?.mfa_enabled ? 'MFA is active on this account.' : 'No second factor is configured.'}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            {profile?.mfa_enabled ? (
              <>
                <input
                  className="form-input"
                  style={{ width: 140, height: 34, fontSize: 12 }}
                  placeholder="TOTP code"
                  value={disableMfaCode}
                  onChange={(event) => setDisableMfaCode(event.target.value)}
                />
                <button className="link-red" onClick={handleDisableMfa} disabled={disablingMfa}>
                  {disablingMfa ? 'Disabling...' : 'Disable'}
                </button>
              </>
            ) : (
              <>
                <span style={{ fontSize: 12, color: 'var(--accent-red)' }}>Disabled</span>
                <Link to="/mfa-setup" className="link-blue">Enable</Link>
              </>
            )}
          </div>
        </div>

        <div style={{ borderBottom: '1px solid var(--border-subtle)', padding: '16px 0' }}>
          <div className="row-between">
            <div>
              <div style={{ fontSize: 14, color: 'var(--text-primary)' }}>Password</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Change your account password.</div>
            </div>
            <button className="link-blue" onClick={() => setShowPwForm((value) => !value)}>{showPwForm ? 'Close' : 'Change Password'}</button>
          </div>
          {showPwForm && (
            <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div className="form-group">
                <label className="form-label">CURRENT PASSWORD</label>
                <input className="form-input" type="password" value={currentPw} onChange={(event) => setCurrentPw(event.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">NEW PASSWORD</label>
                <input className="form-input" type="password" value={newPw} onChange={(event) => setNewPw(event.target.value)} />
                <PwStrength pw={newPw} />
              </div>
              <div className="form-group">
                <label className="form-label">CONFIRM NEW PASSWORD</label>
                <input className="form-input" type="password" value={confirmPw} onChange={(event) => setConfirmPw(event.target.value)} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button className="btn btn-primary btn-sm" style={{ width: 160 }} onClick={handlePasswordChange} disabled={savingPassword}>
                  {savingPassword ? 'Updating...' : 'Update Password'}
                </button>
              </div>
            </div>
          )}
        </div>

        <div style={{ paddingTop: 16 }}>
          <div className="row-between" style={{ alignItems: 'flex-start', gap: 16 }}>
            <div>
              <div style={{ fontSize: 14, color: 'var(--text-primary)' }}>Account Management</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                Export a full copy of your account data or request account deletion.
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-outline btn-sm" onClick={() => void handleExportData()} disabled={exporting}>
                {exporting ? 'Exporting...' : 'Export My Data'}
              </button>
              <button className="btn btn-outline btn-sm" style={{ color: 'var(--accent-red)', borderColor: 'var(--accent-red)' }} onClick={() => void handleDeleteAccount()} disabled={deleting}>
                {deleting ? 'Deleting...' : 'Delete Account'}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 24 }}>
        <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-primary)' }}>Active Sessions</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>Refresh-token sessions currently associated with your account.</div>
        <div style={{ marginTop: 16 }}>
          {sessions.length > 0 ? sessions.map((session) => (
            <div key={session.id} className="row-between" style={{ borderBottom: '1px solid var(--border-subtle)', minHeight: 56, gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {isMobileSession(session) ? <Smartphone size={16} color="var(--text-muted)" /> : <Laptop size={16} color="var(--text-muted)" />}
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {session.device}
                    {session.is_current && <span style={{ fontSize: 11, color: 'var(--accent-green)' }}>(Current)</span>}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {session.browser || 'Unknown browser'} · {session.ip_address || '—'} · Last active {formatRelativeTime(session.last_active)}
                  </div>
                </div>
              </div>
              {!session.is_current && (
                <button className="link-red" onClick={() => void handleRevokeSession(session.id)} disabled={actionId === session.id}>
                  {actionId === session.id ? 'Revoking...' : 'Revoke'}
                </button>
              )}
            </div>
          )) : (
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 8 }}>
              {loading ? 'Loading sessions...' : 'No active refresh-token sessions found.'}
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ padding: 24 }}>
        <div className="row-between" style={{ marginBottom: 16 }}>
          <span style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-primary)' }}>Recent Activity</span>
          <Link to="/audit-logs" className="link-blue">View Audit Logs</Link>
        </div>
        {activity.length > 0 ? activity.map((entry) => (
          <div key={entry.id} className="timeline-item">
            <div className="timeline-dot" style={{ background: 'var(--accent-blue)' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>{humanizeAction(entry.action)}</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{formatDetails(entry.details)}</div>
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)', flexShrink: 0 }}>{formatRelativeTime(entry.created_at)}</div>
          </div>
        )) : (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            {loading ? 'Loading activity...' : 'No recent profile activity yet.'}
          </div>
        )}
      </div>
    </div>
  );
}
