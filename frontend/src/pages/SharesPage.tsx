import { useEffect, useMemo, useState } from 'react';
import { X } from 'lucide-react';

import { shareApi } from '../api';
import client from '../api/client';
import type { ShareLink, ShareStatus } from '../types';
import { getApiErrorMessage } from '../utils/apiError';
import { formatDateTime } from '../utils/formatters';

type AccessLog = {
  id?: string;
  accessed_at: string;
  ip_address?: string;
  user_agent?: string;
};

type DetailedShare = ShareLink & {
  access_logs?: AccessLog[];
};

const STATUS_COLOR: Record<ShareStatus, string> = {
  active: 'var(--accent-green)',
  expired: 'var(--accent-red)',
  revoked: 'var(--text-muted)',
};

type FilterOption = 'All' | 'Active' | 'Expired' | 'Revoked';

function normalizeAccessLogs(payload: unknown): AccessLog[] {
  if (Array.isArray(payload)) {
    return payload as AccessLog[];
  }
  if (payload && typeof payload === 'object' && Array.isArray((payload as { items?: unknown[] }).items)) {
    return (payload as { items: AccessLog[] }).items;
  }
  return [];
}

export default function SharesPage() {
  const [shares, setShares] = useState<ShareLink[]>([]);
  const [filter, setFilter] = useState<FilterOption>('All');
  const [search, setSearch] = useState('');
  const [selectedShare, setSelectedShare] = useState<DetailedShare | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionId, setActionId] = useState<string | null>(null);

  const loadShares = async (nextPage: number) => {
    const response = await shareApi.mine(nextPage);
    setShares(response.data.items);
    setPages(response.data.pages || 1);
    setTotal(response.data.total);
  };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await shareApi.mine(page);
        if (cancelled) {
          return;
        }
        setShares(response.data.items);
        setPages(response.data.pages || 1);
        setTotal(response.data.total);
      } catch (err) {
        if (!cancelled) {
          setShares([]);
          setPages(1);
          setTotal(0);
          setError(getApiErrorMessage(err, 'Share data is unavailable.'));
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

  const stats = useMemo(() => {
    const now = Date.now();
    return {
      active: shares.filter((share) => share.status === 'active').length,
      totalAccesses: shares.reduce((sum, share) => sum + share.current_access_count, 0),
      expiring: shares.filter((share) => {
        if (share.status !== 'active' || !share.expires_at) {
          return false;
        }
        const expiresAt = new Date(share.expires_at).getTime();
        return !Number.isNaN(expiresAt) && expiresAt - now <= 24 * 60 * 60 * 1000;
      }).length,
    };
  }, [shares]);

  const filtered = useMemo(() => {
    return shares.filter((share) => {
      if (filter !== 'All' && share.status !== filter.toLowerCase()) {
        return false;
      }
      if (search) {
        const query = search.toLowerCase();
        const haystack = `${share.file_name || ''} ${share.content_preview} ${share.token_prefix} ${share.payload_id}`.toLowerCase();
        if (!haystack.includes(query)) {
          return false;
        }
      }
      return true;
    });
  }, [filter, search, shares]);

  const loadAccessLogs = async (shareId: string) => {
    try {
      const response = await client.get(`/api/share/${shareId}/access-logs`);
      return normalizeAccessLogs(response.data);
    } catch {
      try {
        const response = await client.get(`/api/admin/shares/${shareId}/access-logs`);
        return normalizeAccessLogs(response.data);
      } catch {
        return [];
      }
    }
  };

  const handleOpenDetails = async (share: ShareLink) => {
    setSelectedShare({ ...share, access_logs: [] });
    setLoadingDetails(true);
    try {
      const [statsResponse, accessLogs] = await Promise.all([
        shareApi.stats(share.id),
        loadAccessLogs(share.id),
      ]);
      setSelectedShare({
        ...(statsResponse.data as ShareLink),
        access_logs: accessLogs,
      });
    } catch {
      setSelectedShare({ ...share, access_logs: [] });
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleRevoke = async (shareId: string) => {
    setActionId(shareId);
    setError('');
    try {
      await shareApi.revoke(shareId);
      await loadShares(page);
      if (selectedShare?.id === shareId) {
        setSelectedShare((current) =>
          current ? { ...current, is_revoked: true, status: 'revoked' } : current,
        );
      }
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not revoke the share link.'));
    } finally {
      setActionId(null);
    }
  };

  const visibleStart = total === 0 ? 0 : (page - 1) * 20 + 1;
  const visibleEnd = total === 0 ? 0 : Math.min(page * 20, total);
  const copyShareLink = async (shareUrl?: string | null) => {
    if (!shareUrl) return;
    await navigator.clipboard.writeText(`${window.location.origin}${shareUrl}`);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="grid-3">
        {[
          { label: 'TOTAL SHARES', value: total, sub: 'Across all pages', color: 'var(--text-primary)' },
          { label: 'ACTIVE ON PAGE', value: stats.active, sub: 'Currently accessible links', color: 'var(--text-primary)' },
          { label: 'EXPIRING SOON', value: stats.expiring, sub: 'Within the next 24 hours', color: 'var(--accent-amber)' },
        ].map(({ label, value, sub, color }) => (
          <div key={label} className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)' }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 500, color, marginTop: 8 }}>{value}</div>
            <div style={{ fontSize: 11, color: label === 'EXPIRING SOON' ? 'var(--accent-amber)' : 'var(--text-muted)', marginTop: 4 }}>{sub}</div>
          </div>
        ))}
      </div>

      <div className="row-between" style={{ gap: 12, flexWrap: 'wrap' }}>
        <div className="search-input-wrap">
          <input
            type="text"
            placeholder="Search by token prefix, payload, or content…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            style={{ width: 320 }}
          />
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 16 }}>
            {(['All', 'Active', 'Expired', 'Revoked'] as const).map((option) => (
              <button
                key={option}
                style={{
                  fontSize: 12,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: filter === option ? 'var(--text-primary)' : 'var(--text-muted)',
                  borderBottom: filter === option ? '2px solid var(--accent-blue)' : '2px solid transparent',
                  paddingBottom: 4,
                }}
                onClick={() => setFilter(option)}
              >
                {option}
              </button>
            ))}
          </div>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Page accesses: {stats.totalAccesses}</span>
        </div>
      </div>

      {error && (
        <div style={{ padding: '10px 14px', background: 'rgba(181,74,74,0.1)', border: '1px solid var(--accent-red)', borderRadius: 2, fontSize: 13, color: 'var(--accent-red)' }}>
          {error}
        </div>
      )}

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>{['CONTENT', 'TOKEN PREFIX', 'CREATED', 'EXPIRES', 'ACCESSES', 'STATUS', 'ACTIONS'].map((heading) => <th key={heading}>{heading}</th>)}</tr>
          </thead>
          <tbody>
            {filtered.length > 0 ? filtered.map((row) => (
              <tr key={row.id}>
                <td style={{ maxWidth: 240 }}>
                  <span className="truncate" style={{ display: 'block' }}>{row.file_name || row.content_preview || 'No preview available'}</span>
                  {row.file_name && row.content_preview && (
                    <span className="truncate" style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{row.content_preview}</span>
                  )}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>{row.token_prefix}…</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>{formatDateTime(row.created_at)}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: row.status === 'expired' ? 'var(--accent-red)' : row.expires_at ? 'var(--text-muted)' : 'var(--accent-blue)' }}>
                  {row.expires_at ? formatDateTime(row.expires_at) : 'Never'}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  {row.current_access_count} / {row.max_access_count ?? '∞'}
                </td>
                <td>
                  <span className="status-dot" style={{ color: STATUS_COLOR[row.status], fontSize: 12 }}>
                    {row.status.charAt(0).toUpperCase() + row.status.slice(1)}
                  </span>
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {row.status === 'active' && (
                      <button className="link-red" onClick={() => void handleRevoke(row.id)} disabled={actionId === row.id}>
                        {actionId === row.id ? 'Revoking…' : 'Revoke'}
                      </button>
                    )}
                    {row.share_url && (
                      <button className="link-blue" onClick={() => void copyShareLink(row.share_url)}>Copy Link</button>
                    )}
                    <button className="link-muted" onClick={() => void handleOpenDetails(row)}>Details</button>
                  </div>
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan={7} style={{ color: 'var(--text-muted)' }}>
                  {loading ? 'Loading share links...' : 'No share links match the current filters.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="pagination">
          <span className="pagination-info">
            Page {page} of {pages} · Server rows {visibleStart}–{visibleEnd}
          </span>
          <div className="pagination-controls">
            <button className="pagination-btn" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page === 1}>← Prev</button>
            <button className="pagination-btn" onClick={() => setPage((value) => Math.min(pages, value + 1))} disabled={page >= pages}>Next →</button>
          </div>
        </div>
      </div>

      {selectedShare && (
        <div className="modal-overlay" onClick={() => setSelectedShare(null)}>
          <div className="modal-box" onClick={(event) => event.stopPropagation()}>
            <button className="modal-close" onClick={() => setSelectedShare(null)}><X size={16} /></button>
            <h3 style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>Share Link Details</h3>
            <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                ['File Name', selectedShare.file_name || 'Text share'],
                ['Content Preview', selectedShare.content_preview || 'No preview available'],
                ['Token Prefix', `${selectedShare.token_prefix}…`],
                ['Payload ID', selectedShare.payload_id],
                ['Password Protected', selectedShare.password_protected ? 'Yes' : 'No'],
                ['Expires', selectedShare.expires_at ? formatDateTime(selectedShare.expires_at) : 'Never'],
                ['Accesses', `${selectedShare.current_access_count} / ${selectedShare.max_access_count ?? '∞'}`],
                ['Status', selectedShare.status],
              ].map(([key, value]) => (
                <div key={key} className="row-between" style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 8, gap: 12 }}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{key}</span>
                  <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', textAlign: 'right' }}>{value}</span>
                </div>
              ))}
            </div>
            {selectedShare.share_url && (
              <div style={{ marginTop: 20, padding: 12, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 8 }}>Share Link</div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <input className="form-input" readOnly value={`${window.location.origin}${selectedShare.share_url}`} />
                  <button className="btn btn-outline btn-sm" type="button" onClick={() => void copyShareLink(selectedShare.share_url)}>
                    Copy Link
                  </button>
                </div>
              </div>
            )}
            <div style={{ marginTop: 16, padding: 12, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 8 }}>Access History</div>
              {loadingDetails ? (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Refreshing access history...</div>
              ) : selectedShare.access_logs && selectedShare.access_logs.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {selectedShare.access_logs.map((entry, index) => (
                    <div key={`${entry.accessed_at}-${index}`} style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 8 }}>
                      <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>{formatDateTime(entry.accessed_at)}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                        {entry.ip_address || 'IP unavailable'} · {entry.user_agent || 'User agent unavailable'}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  No access-log entries are available for this share yet.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
