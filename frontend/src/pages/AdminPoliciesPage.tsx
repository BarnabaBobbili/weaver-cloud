import { useEffect, useMemo, useState } from 'react';

import { policiesApi } from '../api';
import { useAuth } from '../context/AuthContext';
import type { CryptoPolicy, SensitivityLevel } from '../types';
import { getApiErrorMessage } from '../utils/apiError';

const LEVEL_COLORS: Record<SensitivityLevel, string> = {
  public: 'var(--accent-green)',
  internal: 'var(--accent-blue)',
  confidential: 'var(--accent-amber)',
  highly_sensitive: 'var(--accent-red)',
};

type PolicyDraft = {
  display_name: string;
  kdf_iterations: string;
  signing_required: boolean;
  require_mfa: boolean;
  description: string;
};

function draftFromPolicy(policy: CryptoPolicy): PolicyDraft {
  return {
    display_name: policy.display_name,
    kdf_iterations: policy.kdf_iterations ? String(policy.kdf_iterations) : '',
    signing_required: policy.signing_required,
    require_mfa: policy.require_mfa,
    description: policy.description || '',
  };
}

export default function AdminPoliciesPage() {
  const { user } = useAuth();
  const [policies, setPolicies] = useState<CryptoPolicy[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, PolicyDraft>>({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await policiesApi.list();
        if (cancelled) return;

        setPolicies(res.data);
        setDrafts(Object.fromEntries(res.data.map((policy) => [policy.id, draftFromPolicy(policy)])));
      } catch (err) {
        if (!cancelled) {
          setPolicies([]);
          setDrafts({});
          setError(getApiErrorMessage(err, 'Policy data is unavailable.'));
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

  const sortedPolicies = useMemo(() => {
    const order: SensitivityLevel[] = ['public', 'internal', 'confidential', 'highly_sensitive'];
    return [...policies].sort((left, right) => order.indexOf(left.sensitivity_level) - order.indexOf(right.sensitivity_level));
  }, [policies]);

  const handleDraftChange = (policyId: string, field: keyof PolicyDraft, value: string | boolean) => {
    setDrafts((current) => ({
      ...current,
      [policyId]: {
        ...current[policyId],
        [field]: value,
      },
    }));
  };

  const handleSave = async (policy: CryptoPolicy) => {
    const draft = drafts[policy.id];
    if (!draft) return;

    setSavingId(policy.id);
    setError('');
    setSuccess('');
    try {
      await policiesApi.update(policy.id, {
        display_name: draft.display_name.trim(),
        kdf_iterations: draft.kdf_iterations ? Number(draft.kdf_iterations) : null,
        signing_required: draft.signing_required,
        require_mfa: draft.require_mfa,
        description: draft.description.trim(),
      });

      const res = await policiesApi.list();
      setPolicies(res.data);
      setDrafts(Object.fromEntries(res.data.map((item) => [item.id, draftFromPolicy(item)])));
      setEditingId(null);
      setSuccess(`Updated ${policy.display_name}.`);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not update the policy.'));
    } finally {
      setSavingId(null);
    }
  };

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

      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{policies.length} policy tiers configured</div>

      {sortedPolicies.length > 0 ? sortedPolicies.map((policy) => {
        const color = LEVEL_COLORS[policy.sensitivity_level];
        const draft = drafts[policy.id] || draftFromPolicy(policy);
        const editing = editingId === policy.id;
        const params = [
          ['ENCRYPTION', policy.encryption_algo],
          ['KEY DERIVATION', policy.key_derivation || '—'],
          ['KDF ITERATIONS', policy.kdf_iterations?.toLocaleString() || '—'],
          ['SIGNING', policy.signing_algo || (policy.signing_required ? 'Required' : '—')],
          ['INTEGRITY HASH', policy.hash_algo],
          ['REQUIRE MFA', policy.require_mfa ? 'Yes' : 'No'],
        ];

        return (
          <div key={policy.id} className="card" style={{ padding: 24, borderLeft: `3px solid ${color}` }}>
            <div className="row-between" style={{ gap: 16, flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>{policy.display_name}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                  sensitivity_level: {policy.sensitivity_level}
                </div>
              </div>
              {user?.role === 'admin' ? (
                <button className="link-blue" onClick={() => setEditingId(editing ? null : policy.id)}>
                  {editing ? 'Close' : 'Edit'}
                </button>
              ) : (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Read-only</span>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginTop: 16 }}>
              {params.map(([key, value]) => (
                <div key={key}>
                  <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)' }}>{key}</div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: key === 'REQUIRE MFA' && value === 'Yes' ? 'var(--accent-amber)' : 'var(--text-primary)', marginTop: 6 }}>
                    {value}
                  </div>
                </div>
              ))}
            </div>

            {editing && user?.role === 'admin' && (
              <div style={{ marginTop: 20, paddingTop: 20, borderTop: '1px solid var(--border-subtle)', display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">DISPLAY NAME</label>
                  <input className="form-input" value={draft.display_name} onChange={(event) => handleDraftChange(policy.id, 'display_name', event.target.value)} />
                </div>
                <div className="form-group">
                  <label className="form-label">KDF ITERATIONS</label>
                  <input className="form-input" value={draft.kdf_iterations} onChange={(event) => handleDraftChange(policy.id, 'kdf_iterations', event.target.value)} />
                </div>
                <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                  <label className="form-label">DESCRIPTION</label>
                  <textarea className="form-textarea" style={{ height: 100 }} value={draft.description} onChange={(event) => handleDraftChange(policy.id, 'description', event.target.value)} />
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-primary)' }}>
                  <input type="checkbox" checked={draft.signing_required} onChange={(event) => handleDraftChange(policy.id, 'signing_required', event.target.checked)} />
                  Signing required
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-primary)' }}>
                  <input type="checkbox" checked={draft.require_mfa} onChange={(event) => handleDraftChange(policy.id, 'require_mfa', event.target.checked)} />
                  Require MFA
                </label>
                <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end' }}>
                  <button className="btn btn-primary btn-sm" style={{ width: 160 }} onClick={() => void handleSave(policy)} disabled={savingId === policy.id}>
                    {savingId === policy.id ? 'Saving...' : 'Save Policy'}
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      }) : (
        <div className="card" style={{ padding: 24, color: 'var(--text-muted)' }}>
          {loading ? 'Loading policy tiers...' : 'No policy tiers were returned.'}
        </div>
      )}
    </div>
  );
}
