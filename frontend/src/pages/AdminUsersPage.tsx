import { useEffect, useMemo, useState } from 'react';
import { Ban, Pencil } from 'lucide-react';

import { adminApi } from '../api';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';
import type { User, UserRole } from '../types';
import { getApiErrorMessage } from '../utils/apiError';
import { formatDate } from '../utils/formatters';

const ROLE_COLOR: Record<UserRole, string> = {
  admin: 'var(--accent-red)',
  analyst: 'var(--accent-blue)',
  viewer: 'var(--text-muted)',
};

function StatusDot({ active, locked }: { active: boolean; locked: boolean }) {
  const color = locked ? 'var(--accent-red)' : active ? 'var(--accent-green)' : 'var(--accent-amber)';
  const label = locked ? 'Locked' : active ? 'Active' : 'Inactive';
  return <span className="status-dot" style={{ color, fontSize: 12 }}>{label}</span>;
}

type CreateForm = {
  full_name: string;
  email: string;
  password: string;
  role: UserRole;
};

const EMPTY_CREATE_FORM: CreateForm = {
  full_name: '',
  email: '',
  password: '',
  role: 'analyst',
};

export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<'All Roles' | 'Admin' | 'Analyst' | 'Viewer'>('All Roles');
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(EMPTY_CREATE_FORM);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editRole, setEditRole] = useState<UserRole>('analyst');
  const [editActive, setEditActive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadUsers = async (nextPage: number) => {
    const response = await adminApi.listUsers(nextPage);
    setUsers(response.data.items);
    setPages(response.data.pages || 1);
    setTotal(response.data.total);
  };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await adminApi.listUsers(page);
        if (cancelled) {
          return;
        }
        setUsers(response.data.items);
        setPages(response.data.pages || 1);
        setTotal(response.data.total);
      } catch (err) {
        if (!cancelled) {
          setUsers([]);
          setPages(1);
          setTotal(0);
          setError(getApiErrorMessage(err, 'User management data is unavailable.'));
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
  }, [page]);

  const filtered = useMemo(() => {
    return users.filter((account) => {
      if (roleFilter !== 'All Roles' && account.role !== roleFilter.toLowerCase()) {
        return false;
      }
      if (search) {
        const query = search.toLowerCase();
        if (!account.full_name.toLowerCase().includes(query) && !account.email.toLowerCase().includes(query)) {
          return false;
        }
      }
      return true;
    });
  }, [roleFilter, search, users]);

  const stats = useMemo(() => ({
    admins: users.filter((account) => account.role === 'admin').length,
    locked: users.filter((account) => account.failed_login_attempts >= 5).length,
    mfaEnabled: users.filter((account) => account.mfa_enabled).length,
  }), [users]);

  const openEditor = (account: User) => {
    setEditingUser(account);
    setEditRole(account.role);
    setEditActive(account.is_active);
  };

  const handleCreateUser = async () => {
    if (!createForm.full_name.trim() || !createForm.email.trim() || !createForm.password.trim()) {
      setError('Name, email, and password are required.');
      return;
    }

    setCreating(true);
    setError('');
    setSuccess('');
    try {
      await adminApi.createUser({
        full_name: createForm.full_name.trim(),
        email: createForm.email.trim(),
        password: createForm.password,
        role: createForm.role,
      });
      setCreateForm(EMPTY_CREATE_FORM);
      setShowCreateForm(false);
      setPage(1);
      await loadUsers(1);
      setSuccess('User created.');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not create the user.'));
    } finally {
      setCreating(false);
    }
  };

  const handleSaveUser = async () => {
    if (!editingUser) {
      return;
    }

    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await adminApi.updateUser(editingUser.id, { role: editRole, is_active: editActive });
      await loadUsers(page);
      setEditingUser(null);
      setSuccess('User updated.');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not update the user.'));
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async (userId: string) => {
    setActionId(userId);
    setError('');
    setSuccess('');
    try {
      await adminApi.deleteUser(userId);
      await loadUsers(page);
      setSuccess('User deactivated.');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not deactivate the user.'));
    } finally {
      setActionId(null);
    }
  };

  const handleElevatedAction = async (userId: string, action: 'reset-mfa' | 'unlock' | 'force-logout', successMessage: string) => {
    setActionId(`${userId}-${action}`);
    setError('');
    setSuccess('');
    try {
      await client.post(`/api/admin/users/${userId}/${action}`);
      await loadUsers(page);
      setSuccess(successMessage);
    } catch (err) {
      setError(getApiErrorMessage(err, `Could not ${action.replace('-', ' ')}.`));
    } finally {
      setActionId(null);
    }
  };

  const visibleStart = total === 0 ? 0 : (page - 1) * 20 + 1;
  const visibleEnd = total === 0 ? 0 : Math.min(page * 20, total);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
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

      <div className="grid-3">
        {[
          { label: 'TOTAL USERS', value: total, sub: `Rows ${visibleStart}–${visibleEnd} on this page`, color: 'var(--text-primary)' },
          { label: 'ADMINS ON PAGE', value: stats.admins, sub: 'Privileged accounts', color: 'var(--accent-red)' },
          { label: 'LOCKED ACCOUNTS', value: stats.locked, sub: `${stats.mfaEnabled} MFA-enabled accounts`, color: 'var(--accent-amber)' },
        ].map(({ label, value, sub, color }) => (
          <div key={label} className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-muted)' }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 500, color, marginTop: 8 }}>{value}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>
          </div>
        ))}
      </div>

      <div className="row-between" style={{ gap: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {total} users total · page {page} of {pages} · rows {visibleStart}–{visibleEnd}
        </span>
        <button className="btn btn-primary btn-sm" onClick={() => setShowCreateForm((value) => !value)}>
          {showCreateForm ? 'Close' : '＋ New User'}
        </button>
      </div>

      {showCreateForm && (
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 16 }}>Create User</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 }}>
            <input className="form-input" placeholder="Full name" value={createForm.full_name} onChange={(event) => setCreateForm((current) => ({ ...current, full_name: event.target.value }))} />
            <input className="form-input" placeholder="Email" value={createForm.email} onChange={(event) => setCreateForm((current) => ({ ...current, email: event.target.value }))} />
            <input className="form-input" placeholder="Password" type="password" value={createForm.password} onChange={(event) => setCreateForm((current) => ({ ...current, password: event.target.value }))} />
            <select className="form-select" value={createForm.role} onChange={(event) => setCreateForm((current) => ({ ...current, role: event.target.value as UserRole }))}>
              <option value="admin">admin</option>
              <option value="analyst">analyst</option>
              <option value="viewer">viewer</option>
            </select>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
            <button className="btn btn-primary btn-sm" style={{ width: 150 }} onClick={handleCreateUser} disabled={creating}>
              {creating ? 'Creating...' : 'Create User'}
            </button>
          </div>
        </div>
      )}

      {editingUser && (
        <div className="card" style={{ padding: 20 }}>
          <div className="row-between" style={{ gap: 16, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>Edit User</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{editingUser.full_name} · {editingUser.email}</div>
            </div>
            <button className="link-muted" onClick={() => setEditingUser(null)}>Close</button>
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <div className="form-group" style={{ minWidth: 180 }}>
              <label className="form-label">ROLE</label>
              <select className="form-select" value={editRole} onChange={(event) => setEditRole(event.target.value as UserRole)}>
                <option value="admin">admin</option>
                <option value="analyst">analyst</option>
                <option value="viewer">viewer</option>
              </select>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-primary)' }}>
              <input type="checkbox" checked={editActive} onChange={(event) => setEditActive(event.target.checked)} />
              Account active
            </label>
            <button className="btn btn-primary btn-sm" style={{ width: 140 }} onClick={handleSaveUser} disabled={saving}>
              {saving ? 'Saving...' : 'Save User'}
            </button>
          </div>

          <div style={{ marginTop: 18, paddingTop: 18, borderTop: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 12 }}>Elevated Actions</div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => void handleElevatedAction(editingUser.id, 'reset-mfa', 'MFA reset.')}
                disabled={actionId === `${editingUser.id}-reset-mfa`}
              >
                {actionId === `${editingUser.id}-reset-mfa` ? 'Resetting...' : 'Reset MFA'}
              </button>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => void handleElevatedAction(editingUser.id, 'unlock', 'Account unlocked.')}
                disabled={actionId === `${editingUser.id}-unlock`}
              >
                {actionId === `${editingUser.id}-unlock` ? 'Unlocking...' : 'Unlock'}
              </button>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => void handleElevatedAction(editingUser.id, 'force-logout', 'All refresh tokens revoked.')}
                disabled={actionId === `${editingUser.id}-force-logout`}
              >
                {actionId === `${editingUser.id}-force-logout` ? 'Revoking...' : 'Force Logout'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="row-between">
        <div className="search-input-wrap">
          <input type="text" placeholder="Search by name or email" value={search} onChange={(event) => setSearch(event.target.value)} style={{ width: 280 }} />
        </div>
        <select className="form-select" style={{ width: 120 }} value={roleFilter} onChange={(event) => setRoleFilter(event.target.value as typeof roleFilter)}>
          <option>All Roles</option>
          <option>Admin</option>
          <option>Analyst</option>
          <option>Viewer</option>
        </select>
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>{['NAME', 'EMAIL', 'ROLE', 'MFA', 'STATUS', 'JOINED', 'ACTIONS'].map((heading) => <th key={heading}>{heading}</th>)}</tr>
          </thead>
          <tbody>
            {filtered.length > 0 ? filtered.map((account) => (
              <tr key={account.id}>
                <td style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{account.full_name}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-secondary)' }}>{account.email}</td>
                <td>
                  <span className="badge" style={{ color: ROLE_COLOR[account.role], borderColor: ROLE_COLOR[account.role], fontSize: 11 }}>
                    {account.role}
                  </span>
                </td>
                <td style={{ fontSize: 12, color: account.mfa_enabled ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                  {account.mfa_enabled ? 'Enabled' : 'Disabled'}
                </td>
                <td>
                  <StatusDot active={account.is_active} locked={account.failed_login_attempts >= 5} />
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>
                  {formatDate(account.created_at)}
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                    <button
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}
                      onMouseOver={(event) => { event.currentTarget.style.color = 'var(--text-primary)'; }}
                      onMouseOut={(event) => { event.currentTarget.style.color = 'var(--text-muted)'; }}
                      onClick={() => openEditor(account)}
                    >
                      <Pencil size={14} />
                    </button>
                    <button className="link-blue" onClick={() => void handleElevatedAction(account.id, 'reset-mfa', 'MFA reset.')}>
                      Reset MFA
                    </button>
                    <button className="link-blue" onClick={() => void handleElevatedAction(account.id, 'unlock', 'Account unlocked.')}>
                      Unlock
                    </button>
                    <button className="link-blue" onClick={() => void handleElevatedAction(account.id, 'force-logout', 'All refresh tokens revoked.')}>
                      Force Logout
                    </button>
                    <button
                      style={{ background: 'none', border: 'none', cursor: currentUser?.id === account.id ? 'not-allowed' : 'pointer', color: currentUser?.id === account.id ? 'var(--text-dim)' : 'var(--text-muted)', display: 'flex' }}
                      onMouseOver={(event) => {
                        if (currentUser?.id !== account.id) {
                          event.currentTarget.style.color = 'var(--accent-red)';
                        }
                      }}
                      onMouseOut={(event) => {
                        event.currentTarget.style.color = currentUser?.id === account.id ? 'var(--text-dim)' : 'var(--text-muted)';
                      }}
                      onClick={() => {
                        if (currentUser?.id !== account.id) {
                          void handleDeactivate(account.id);
                        }
                      }}
                      disabled={currentUser?.id === account.id || actionId === account.id}
                    >
                      <Ban size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan={7} style={{ color: 'var(--text-muted)' }}>
                  {loading ? 'Loading users...' : 'No users match the current filters.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="pagination">
          <span className="pagination-info">Filtered rows on this page: {filtered.length}</span>
          <div className="pagination-controls">
            <button className="pagination-btn" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page === 1}>← Prev</button>
            <button className="pagination-btn" onClick={() => setPage((value) => Math.min(pages, value + 1))} disabled={page >= pages}>Next →</button>
          </div>
        </div>
      </div>
    </div>
  );
}
