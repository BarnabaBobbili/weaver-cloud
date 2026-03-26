import { Fragment, useEffect, useState } from 'react';

import client from '../api/client';
import { policiesApi } from '../api';
import type { ClassificationRecord, CryptoPolicy, SensitivityLevel } from '../types';
import { getApiErrorMessage } from '../utils/apiError';
import { formatDateTime } from '../utils/formatters';

const LEVEL_COLOR: Record<SensitivityLevel, string> = {
  public: 'var(--accent-green)',
  internal: 'var(--accent-blue)',
  confidential: 'var(--accent-amber)',
  highly_sensitive: 'var(--accent-red)',
};

function downloadFile(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

type HistoryResponse = {
  items: ClassificationRecord[];
  total: number;
  page: number;
  pages: number;
};

export default function HistoryPage() {
  const [rows, setRows] = useState<ClassificationRecord[]>([]);
  const [policiesById, setPoliciesById] = useState<Record<string, CryptoPolicy>>({});
  const [search, setSearch] = useState('');
  const [levelFilter, setLevelFilter] = useState<'' | SensitivityLevel>('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
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
        const [historyResponse, policiesResponse] = await Promise.all([
          client.get<HistoryResponse>('/api/classify/history', {
            params: {
              page,
              limit: 10,
              search: search || undefined,
              level: levelFilter || undefined,
              from_date: fromDate || undefined,
              to_date: toDate || undefined,
            },
          }),
          policiesApi.list(),
        ]);

        if (cancelled) {
          return;
        }

        setRows(historyResponse.data.items);
        setPages(historyResponse.data.pages || 1);
        setTotal(historyResponse.data.total);
        setPoliciesById(
          Object.fromEntries(policiesResponse.data.map((policy) => [policy.id, policy])),
        );
      } catch (err) {
        if (!cancelled) {
          setRows([]);
          setPages(1);
          setTotal(0);
          setPoliciesById({});
          setError(getApiErrorMessage(err, 'Classification history is unavailable.'));
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
  }, [fromDate, levelFilter, page, search, toDate]);

  const exportJson = () => {
    downloadFile(`classification-history-page-${page}.json`, JSON.stringify(rows, null, 2), 'application/json;charset=utf-8;');
  };

  const exportCsv = () => {
    const header = ['date', 'input_preview', 'input_type', 'level', 'confidence', 'policy'];
    const body = rows.map((row) => {
      const policy = policiesById[row.policy_applied_id];
      return [
        formatDateTime(row.created_at),
        row.input_text_preview,
        row.input_type,
        row.predicted_level,
        `${(row.confidence_score * 100).toFixed(1)}%`,
        policy?.encryption_algo || row.policy_applied_id,
      ];
    });

    const csv = [header, ...body]
      .map((line) => line.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(','))
      .join('\n');

    downloadFile(`classification-history-page-${page}.csv`, csv, 'text/csv;charset=utf-8;');
  };

  const visibleStart = total === 0 ? 0 : (page - 1) * 10 + 1;
  const visibleEnd = total === 0 ? 0 : Math.min(page * 10, total);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="row-between" style={{ gap: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Your Classification History · {total.toLocaleString()} matching records
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={exportCsv} disabled={rows.length === 0}>Export CSV</button>
          <button className="btn btn-ghost btn-sm" onClick={exportJson} disabled={rows.length === 0}>Export JSON</button>
        </div>
      </div>

      <div className="filter-bar" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 12 }}>
        <div className="search-input-wrap">
          <input
            type="text"
            placeholder="Search by content preview or file name…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            style={{ width: '100%' }}
          />
        </div>
        <select className="form-select" value={levelFilter} onChange={(event) => {
          setLevelFilter(event.target.value as '' | SensitivityLevel);
          setPage(1);
        }}>
          <option value="">All levels</option>
          <option value="public">Public</option>
          <option value="internal">Internal</option>
          <option value="confidential">Confidential</option>
          <option value="highly_sensitive">Highly Sensitive</option>
        </select>
        <input className="form-input" type="date" value={fromDate} onChange={(event) => {
          setFromDate(event.target.value);
          setPage(1);
        }} />
        <input className="form-input" type="date" value={toDate} onChange={(event) => {
          setToDate(event.target.value);
          setPage(1);
        }} />
      </div>

      {error && (
        <div style={{ padding: '10px 14px', background: 'rgba(181,74,74,0.1)', border: '1px solid var(--accent-red)', borderRadius: 2, fontSize: 13, color: 'var(--accent-red)' }}>
          {error}
        </div>
      )}

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              {['DATE', 'INPUT PREVIEW', 'TYPE', 'LEVEL', 'CONFIDENCE', 'POLICY', 'ACTIONS'].map((heading) => <th key={heading}>{heading}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? rows.map((row) => {
              const color = LEVEL_COLOR[row.predicted_level as SensitivityLevel];
              const isExpanded = expandedId === row.id;
              const policy = policiesById[row.policy_applied_id];

              return (
                <Fragment key={row.id}>
                  <tr>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>{formatDateTime(row.created_at)}</td>
                    <td style={{ maxWidth: 320 }}>
                      <div className="truncate" style={{ display: 'block' }}>{row.input_text_preview}</div>
                      {row.file_name && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{row.file_name}</div>}
                    </td>
                    <td>
                      <span className="badge" style={{ color: row.input_type === 'text' ? 'var(--accent-blue)' : 'var(--text-muted)', borderColor: row.input_type === 'text' ? 'var(--accent-blue)' : 'var(--text-muted)' }}>
                        {row.input_type}
                      </span>
                    </td>
                    <td>
                      <span className="badge" style={{ color, borderColor: color }}>{row.predicted_level.replace('_', ' ')}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ width: 60, height: 4, background: 'var(--border-subtle)', borderRadius: 1 }}>
                          <div style={{ width: `${row.confidence_score * 100}%`, height: '100%', background: color, borderRadius: 1 }} />
                        </div>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{(row.confidence_score * 100).toFixed(1)}%</span>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>
                      {policy?.encryption_algo || row.policy_applied_id}
                    </td>
                    <td>
                      <button className="link-blue" onClick={() => setExpandedId(isExpanded ? null : row.id)}>
                        {isExpanded ? 'Hide' : 'View'}
                      </button>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan={7} style={{ padding: 0, borderBottom: '1px solid var(--border-subtle)' }}>
                        <div style={{ background: 'var(--bg-primary)', padding: 20, display: 'grid', gridTemplateColumns: '60% 40%', gap: 24 }}>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 8 }}>Explanation Summary</div>
                            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{row.explanation_summary}</p>
                            {row.explanation_details && row.explanation_details.length > 0 && (
                              <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {row.explanation_details.map((factor) => (
                                  <div key={`${row.id}-${factor.feature}`} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12 }}>
                                    <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{factor.feature}</span>
                                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>{factor.weight.toFixed(2)}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 8 }}>Policy Applied</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                              <div style={{ fontSize: 13, color: 'var(--text-primary)' }}>{policy?.display_name || 'Policy unavailable'}</div>
                              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>
                                {policy ? `${policy.encryption_algo} · ${policy.key_derivation || 'No KDF'} · ${policy.hash_algo}` : row.policy_applied_id}
                              </div>
                              {policy && (
                                <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                                  Signing: {policy.signing_required ? policy.signing_algo || 'Required' : 'Not required'}
                                  <br />
                                  MFA Required: {policy.require_mfa ? 'Yes' : 'No'}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            }) : (
              <tr>
                <td colSpan={7} style={{ color: 'var(--text-muted)' }}>
                  {loading ? 'Loading classification history...' : 'No classification records match the current filters.'}
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
    </div>
  );
}
