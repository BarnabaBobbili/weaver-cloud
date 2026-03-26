import { Fragment, useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

import { analyticsApi } from '../api';
import type { AuditLog, AuditSeverity } from '../types';
import { getApiErrorMessage } from '../utils/apiError';
import { formatDateTime } from '../utils/formatters';

const ACTION_COLOR: Record<string, string> = {
  login: '#6B7280',
  login_failed: '#B54A4A',
  classify: '#4A7C8F',
  classify_file: '#4A7C8F',
  encrypt: '#5B8A72',
  decrypt: '#5B8A72',
  share_create: '#D4914B',
  share_access: '#D4914B',
  register: '#4A7C8F',
  logout: '#6B7280',
};

const SEV_COLOR: Record<AuditSeverity, string> = {
  info: 'var(--accent-blue)',
  warning: 'var(--accent-amber)',
  critical: 'var(--accent-red)',
};

const ALL_SEVERITIES: AuditSeverity[] = ['info', 'warning', 'critical'];

function downloadFile(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [actionFilter, setActionFilter] = useState('All Actions');
  const [severities, setSeverities] = useState<AuditSeverity[]>(ALL_SEVERITIES);
  const [userFilter, setUserFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await analyticsApi.auditLogs({
          page,
          limit: 20,
          ...(actionFilter !== 'All Actions' ? { action: actionFilter.toLowerCase() } : {}),
        });

        if (cancelled) return;

        setLogs(res.data.items);
        setPages(res.data.pages || 1);
        setTotal(res.data.total);
      } catch (err) {
        if (!cancelled) {
          setLogs([]);
          setPages(1);
          setTotal(0);
          setError(getApiErrorMessage(err, 'Audit log data is unavailable.'));
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
  }, [actionFilter, page]);

  const filtered = useMemo(() => {
    return logs.filter((log) => {
      if (!severities.includes(log.severity)) return false;

      const userLabel = `${log.user_email || ''} ${log.user_id || ''}`.toLowerCase();
      if (userFilter && !userLabel.includes(userFilter.toLowerCase())) return false;

      const createdAt = new Date(log.created_at);
      if (dateFrom) {
        const from = new Date(`${dateFrom}T00:00:00`);
        if (createdAt < from) return false;
      }
      if (dateTo) {
        const to = new Date(`${dateTo}T23:59:59`);
        if (createdAt > to) return false;
      }

      return true;
    });
  }, [dateFrom, dateTo, logs, severities, userFilter]);

  const toggleSeverity = (severity: AuditSeverity) => {
    setSeverities((prev) =>
      prev.includes(severity) ? prev.filter((value) => value !== severity) : [...prev, severity]
    );
  };

  const clearFilters = () => {
    setActionFilter('All Actions');
    setSeverities(ALL_SEVERITIES);
    setUserFilter('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

  const exportCsv = () => {
    const header = ['timestamp', 'user', 'action', 'resource', 'ip_address', 'severity', 'details'];
    const rows = filtered.map((log) => [
      formatDateTime(log.created_at),
      log.user_email || log.user_id || 'system',
      log.action,
      [log.resource_type, log.resource_id].filter(Boolean).join('/') || '—',
      log.ip_address || '—',
      log.severity,
      JSON.stringify(log.details || {}),
    ]);

    const csv = [header, ...rows]
      .map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(','))
      .join('\n');

    downloadFile(`audit-logs-page-${page}.csv`, csv, 'text/csv;charset=utf-8;');
  };

  const exportJson = () => {
    downloadFile(`audit-logs-page-${page}.json`, JSON.stringify(filtered, null, 2), 'application/json;charset=utf-8;');
  };

  const visibleStart = total === 0 ? 0 : (page - 1) * 20 + 1;
  const visibleEnd = total === 0 ? 0 : Math.min(page * 20, total);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="row-between" style={{ gap: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Security Audit Log · {total.toLocaleString()} events recorded
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={exportCsv} disabled={filtered.length === 0}>Export CSV</button>
          <button className="btn btn-ghost btn-sm" onClick={exportJson} disabled={filtered.length === 0}>Export JSON</button>
        </div>
      </div>

      <div className="filter-bar">
        <select
          className="form-select"
          style={{ width: 160 }}
          value={actionFilter}
          onChange={(event) => {
            setActionFilter(event.target.value);
            setPage(1);
          }}
        >
          {['All Actions', 'LOGIN', 'REGISTER', 'CLASSIFY', 'CLASSIFY_FILE', 'ENCRYPT', 'DECRYPT', 'SHARE_CREATE', 'LOGOUT'].map((option) => (
            <option key={option}>{option}</option>
          ))}
        </select>

        <div style={{ display: 'flex', gap: 8 }}>
          {ALL_SEVERITIES.map((severity) => (
            <button
              key={severity}
              className={`toggle-chip ${severities.includes(severity) ? '' : 'inactive'}`}
              style={{
                color: SEV_COLOR[severity],
                borderColor: SEV_COLOR[severity],
                background: severities.includes(severity) ? `${SEV_COLOR[severity]}22` : 'transparent',
              }}
              onClick={() => toggleSeverity(severity)}
            >
              {severity.charAt(0).toUpperCase() + severity.slice(1)}
            </button>
          ))}
        </div>

        <input
          type="text"
          placeholder="Filter by user…"
          value={userFilter}
          onChange={(event) => setUserFilter(event.target.value)}
          style={{ height: 32, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 2, color: 'var(--text-primary)', fontSize: 12, padding: '0 8px', width: 180, outline: 'none' }}
        />

        <div style={{ display: 'flex', gap: 8 }}>
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} style={{ height: 32, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 2, color: 'var(--text-muted)', fontSize: 12, padding: '0 8px', width: 132 }} />
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} style={{ height: 32, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', borderRadius: 2, color: 'var(--text-muted)', fontSize: 12, padding: '0 8px', width: 132 }} />
        </div>

        <button className="link-muted" style={{ marginLeft: 'auto' }} onClick={clearFilters}>Clear Filters</button>
      </div>

      {error && (
        <div style={{ padding: '10px 14px', background: 'rgba(181,74,74,0.1)', border: '1px solid var(--accent-red)', borderRadius: 2, fontSize: 13, color: 'var(--accent-red)' }}>
          {error}
        </div>
      )}

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>{['TIMESTAMP', 'USER', 'ACTION', 'RESOURCE', 'IP ADDRESS', 'SEVERITY', 'DETAILS'].map((heading) => <th key={heading}>{heading}</th>)}</tr>
          </thead>
          <tbody>
            {filtered.length > 0 ? filtered.map((row) => {
              const isExpanded = expandedId === row.id;
              const resource = [row.resource_type, row.resource_id].filter(Boolean).join('/') || '—';
              const actionColor = ACTION_COLOR[row.action] || 'var(--accent-blue)';

              return (
                <Fragment key={row.id}>
                  <tr
                    className={row.severity === 'critical' ? 'row-critical' : row.severity === 'warning' ? 'row-warning' : ''}
                    style={{ borderLeft: row.severity === 'critical' ? '3px solid var(--accent-red)' : row.severity === 'warning' ? '3px solid var(--accent-amber)' : undefined }}
                  >
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>{formatDateTime(row.created_at)}</td>
                    <td style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{row.user_email || row.user_id || 'system'}</td>
                    <td>
                      <span className="badge" style={{ color: actionColor, borderColor: actionColor, fontSize: 11 }}>
                        {row.action}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)', maxWidth: 200 }}>
                      <span className="truncate" style={{ display: 'block' }}>{resource}</span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>{row.ip_address || '—'}</td>
                    <td style={{ fontSize: 12, color: SEV_COLOR[row.severity] }}>{row.severity}</td>
                    <td>
                      <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }} onClick={() => setExpandedId(isExpanded ? null : row.id)}>
                        {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      </button>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={7} style={{ padding: 0 }}>
                        <div style={{ background: 'var(--bg-primary)', padding: 12, borderTop: '1px solid var(--border-subtle)' }}>
                          <pre style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)', margin: 0, whiteSpace: 'pre-wrap' }}>
                            {JSON.stringify(row.details || {}, null, 2)}
                          </pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            }) : (
              <tr>
                <td colSpan={7} style={{ color: 'var(--text-muted)' }}>
                  {loading ? 'Loading audit logs...' : 'No audit logs match the current filters.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="pagination">
          <span className="pagination-info">
            Page {page} of {pages} · Server rows {visibleStart}–{visibleEnd} · {filtered.length} visible after filters
          </span>
          <div className="pagination-controls">
            <button className="pagination-btn" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page === 1}>← Prev</button>
            <button className="pagination-btn" onClick={() => setPage((value) => Math.min(pages, value + 1))} disabled={page >= pages}>Next →</button>
          </div>
        </div>
      </div>
    </div>
  );
}
