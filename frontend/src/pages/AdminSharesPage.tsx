import { useEffect, useState } from 'react';

import { adminApi } from '../api';
import type { ShareAccessLog, ShareLink } from '../types';
import { formatDateTime } from '../utils/formatters';

export default function AdminSharesPage() {
  const [shares, setShares] = useState<ShareLink[]>([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<ShareLink | null>(null);
  const [logs, setLogs] = useState<ShareAccessLog[]>([]);

  const load = () => {
    adminApi.shares(1, search).then((res) => setShares(res.data.items)).catch(() => setShares([]));
  };

  useEffect(() => {
    load();
  }, []);

  const handleOpen = async (share: ShareLink) => {
    setSelected(share);
    const res = await adminApi.shareAccessLogs(share.id).catch(() => ({ data: { items: [] } }));
    setLogs(res.data.items);
  };

  const copyShareLink = async (shareUrl?: string | null) => {
    if (!shareUrl) return;
    await navigator.clipboard.writeText(`${window.location.origin}${shareUrl}`);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="row-between">
        <div className="search-input-wrap">
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by owner, preview, token prefix" style={{ width: 320 }} />
        </div>
        <button className="btn btn-primary btn-sm" onClick={load}>Refresh</button>
      </div>
      <div className="card">
        <table className="data-table">
          <thead>
            <tr>{['OWNER', 'CONTENT', 'TOKEN', 'EXPIRES', 'ACCESSES', 'STATUS', 'ACTIONS'].map((heading) => <th key={heading}>{heading}</th>)}</tr>
          </thead>
          <tbody>
            {shares.length > 0 ? shares.map((share) => (
              <tr key={share.id}>
                <td>{share.owner_email || 'Guest'}</td>
                <td style={{ maxWidth: 240 }}>
                  <span className="truncate" style={{ display: 'block' }}>{share.file_name || share.content_preview || 'No preview'}</span>
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{share.token_prefix}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{share.expires_at ? formatDateTime(share.expires_at) : 'Never'}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{share.current_access_count} / {share.max_access_count ?? '∞'}</td>
                <td>{share.status}</td>
                <td>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="link-blue" onClick={() => void handleOpen(share)}>Logs</button>
                    {share.share_url && <button className="link-blue" onClick={() => void copyShareLink(share.share_url)}>Copy Link</button>}
                    {share.status === 'active' && <button className="link-red" onClick={() => void adminApi.revokeShare(share.id).then(load).catch(() => {})}>Revoke</button>}
                  </div>
                </td>
              </tr>
            )) : (
              <tr><td colSpan={7} style={{ color: 'var(--text-muted)' }}>No shares found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal-box" onClick={(event) => event.stopPropagation()}>
            <h3 style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>Access Logs</h3>
            <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>File / Content</div>
              <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>{selected.file_name || selected.content_preview || 'No preview'}</div>
              {selected.share_url && (
                <div style={{ display: 'flex', gap: 10 }}>
                  <input className="form-input" readOnly value={`${window.location.origin}${selected.share_url}`} />
                  <button className="btn btn-outline btn-sm" type="button" onClick={() => void copyShareLink(selected.share_url)}>
                    Copy Link
                  </button>
                </div>
              )}
            </div>
            <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {logs.length > 0 ? logs.map((log) => (
                <div key={log.id} className="row-between" style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: 8, gap: 12 }}>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{formatDateTime(log.accessed_at)}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{log.ip_address || 'unknown ip'}</span>
                </div>
              )) : (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No access logs yet.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
