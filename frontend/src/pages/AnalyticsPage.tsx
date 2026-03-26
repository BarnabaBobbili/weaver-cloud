import { useEffect, useMemo, useState } from 'react';
import { BarChart3, Layers, Lock, ShieldAlert } from 'lucide-react';

import { analyticsApi, profileApi } from '../api';
import type { AlgorithmUsage, AnalyticsOverview, AuditLog, ProfileActivityItem, SensitivityDistribution, TimeSeriesPoint } from '../types';
import { formatDetails, formatRelativeTime, humanizeAction } from '../utils/formatters';

const RANGES = ['7D', '30D', '90D'] as const;

type RangeOption = (typeof RANGES)[number];

type ActivityRow = {
  id: string;
  action: string;
  details: unknown;
  created_at: string;
  source: 'audit' | 'profile';
};

const EMPTY_OVERVIEW: AnalyticsOverview = {
  total_classifications: 0,
  total_encryptions: 0,
  active_shares: 0,
  total_users: 0,
  classifications_this_week: 0,
  encryptions_this_week: 0,
  expiring_shares: 0,
  classifications_this_month: 0,
  avg_confidence: null,
  most_common_level: null,
  most_common_pct: 0,
};

const EMPTY_DISTRIBUTION: SensitivityDistribution = {
  public: 0,
  internal: 0,
  confidential: 0,
  highly_sensitive: 0,
};

const LEVEL_COLOR: Record<keyof SensitivityDistribution, string> = {
  public: 'var(--accent-green)',
  internal: 'var(--accent-blue)',
  confidential: 'var(--accent-amber)',
  highly_sensitive: 'var(--accent-red)',
};

function normalizeActivity(items: ProfileActivityItem[], source: ActivityRow['source']): ActivityRow[] {
  return items.map((item) => ({
    id: item.id,
    action: item.action,
    details: item.details,
    created_at: item.created_at,
    source,
  }));
}

function normalizeAuditActivity(items: AuditLog[]): ActivityRow[] {
  return items.map((item) => ({
    id: item.id,
    action: item.action,
    details: item.details,
    created_at: item.created_at,
    source: 'audit',
  }));
}

export default function AnalyticsPage() {
  const [range, setRange] = useState<RangeOption>('30D');
  const [overview, setOverview] = useState<AnalyticsOverview>(EMPTY_OVERVIEW);
  const [distribution, setDistribution] = useState<SensitivityDistribution>(EMPTY_DISTRIBUTION);
  const [timeseries, setTimeseries] = useState<TimeSeriesPoint[]>([]);
  const [algorithms, setAlgorithms] = useState<AlgorithmUsage[]>([]);
  const [activity, setActivity] = useState<ActivityRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError('');

      try {
        const [overviewRes, distributionRes, timeseriesRes, algorithmsRes] = await Promise.all([
          analyticsApi.overview(),
          analyticsApi.sensitivityDistribution(range),
          analyticsApi.sensitivityTimeseries(range),
          analyticsApi.algorithmUsage(),
        ]);

        if (cancelled) return;

        setOverview(overviewRes.data);
        setDistribution(distributionRes.data);
        setTimeseries(timeseriesRes.data.items);
        setAlgorithms(algorithmsRes.data);

        try {
          const auditRes = await analyticsApi.auditLogs({ page: 1, limit: 6 });
          if (!cancelled) {
            setActivity(normalizeAuditActivity(auditRes.data.items));
          }
        } catch {
          const profileRes = await profileApi.activity(1);
          if (!cancelled) {
            setActivity(normalizeActivity(profileRes.data.items.slice(0, 6), 'profile'));
          }
        }
      } catch {
        if (!cancelled) {
          setError('Analytics data is unavailable right now.');
          setOverview(EMPTY_OVERVIEW);
          setDistribution(EMPTY_DISTRIBUTION);
          setTimeseries([]);
          setAlgorithms([]);
          setActivity([]);
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
  }, [range]);

  const distributionRows = useMemo(() => {
    const total = Object.values(distribution).reduce((sum, count) => sum + count, 0);
    return (Object.entries(distribution) as Array<[keyof SensitivityDistribution, number]>).map(([level, count]) => ({
      level,
      count,
      pct: total ? Math.round((count / total) * 100) : 0,
      color: LEVEL_COLOR[level],
    }));
  }, [distribution]);

  const algorithmRows = useMemo(() => {
    const maxCount = Math.max(1, ...algorithms.map((item) => item.count));
    return algorithms.map((item) => ({
      ...item,
      width: Math.max(8, Math.round((item.count / maxCount) * 100)),
    }));
  }, [algorithms]);

  const timelineRows = useMemo(() => {
    const maxCount = Math.max(
      1,
      ...timeseries.map((point) => point.public + point.internal + point.confidential + point.highly_sensitive)
    );

    return timeseries.map((point) => {
      const total = point.public + point.internal + point.confidential + point.highly_sensitive;
      return {
        ...point,
        total,
        width: Math.max(6, Math.round((total / maxCount) * 100)),
      };
    });
  }, [timeseries]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="row-between" style={{ gap: 16, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>Operational Analytics</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            Live security, classification, and encryption activity.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {RANGES.map((option) => (
            <button
              key={option}
              className={`toggle-chip ${range === option ? '' : 'inactive'}`}
              style={{
                color: range === option ? 'var(--accent-blue)' : 'var(--text-muted)',
                borderColor: 'var(--border-subtle)',
                background: range === option ? 'rgba(74,124,143,0.12)' : 'transparent',
              }}
              onClick={() => setRange(option)}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div style={{ padding: '10px 14px', background: 'rgba(181,74,74,0.1)', border: '1px solid var(--accent-red)', borderRadius: 2, fontSize: 13, color: 'var(--accent-red)' }}>
          {error}
        </div>
      )}

      <div className="grid-4">
        {[
          {
            label: '30D CLASSIFICATIONS',
            value: overview.classifications_this_month.toLocaleString(),
            sub: `${overview.classifications_this_week} in the last 7 days`,
            icon: <Layers size={14} />,
          },
          {
            label: 'AVERAGE CONFIDENCE',
            value: overview.avg_confidence === null ? '—' : `${(overview.avg_confidence * 100).toFixed(1)}%`,
            sub: 'Computed from recent classifications',
            icon: <BarChart3 size={14} />,
          },
          {
            label: 'ENCRYPTIONS',
            value: overview.total_encryptions.toLocaleString(),
            sub: `${overview.encryptions_this_week} in the last 7 days`,
            icon: <Lock size={14} />,
          },
          {
            label: 'MOST COMMON LEVEL',
            value: overview.most_common_level ? overview.most_common_level.replace('_', ' ') : '—',
            sub: overview.most_common_level ? `${overview.most_common_pct}% of all classifications` : 'No classifications yet',
            icon: <ShieldAlert size={14} />,
          },
        ].map(({ label, value, sub, icon }) => (
          <div key={label} className="stat-block">
            <div className="stat-label">{icon}{label}</div>
            <div className="stat-value" style={{ textTransform: 'capitalize' }}>{value}</div>
            <div className="stat-sub">{sub}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '58% 42%', gap: 16 }}>
        <div className="card" style={{ padding: 24 }}>
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>Classification Trend</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Daily totals split by sensitivity level</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 20 }}>
            {timelineRows.length > 0 ? timelineRows.map((point) => (
              <div key={point.date} style={{ display: 'grid', gridTemplateColumns: '72px 1fr 44px', gap: 12, alignItems: 'center' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{point.date}</span>
                <div style={{ width: '100%', height: 12, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', overflow: 'hidden', display: 'flex' }}>
                  {(['public', 'internal', 'confidential', 'highly_sensitive'] as Array<keyof SensitivityDistribution>).map((level) => {
                    const count = point[level];
                    const total = point.total || 1;
                    if (!count) return null;
                    return (
                      <div
                        key={level}
                        style={{
                          width: `${(count / total) * point.width}%`,
                          background: LEVEL_COLOR[level],
                        }}
                      />
                    );
                  })}
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{point.total}</span>
              </div>
            )) : (
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                {loading ? 'Loading trend data...' : 'No classification trend data yet.'}
              </div>
            )}
          </div>
        </div>

        <div className="card" style={{ padding: 24 }}>
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>Sensitivity Mix</div>
          <div className="stacked-bar" style={{ marginTop: 20 }}>
            {distributionRows.map((row) => (
              <div key={row.level} className="stacked-bar-seg" style={{ width: `${row.pct}%`, background: row.color }}>
                {row.pct >= 10 ? `${row.pct}%` : ''}
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 18 }}>
            {distributionRows.map((row) => (
              <div key={row.level} style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 8, alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 8, height: 8, background: row.color, borderRadius: 1 }} />
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                    {row.level.replace('_', ' ')}
                  </span>
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{row.count}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>{row.pct}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '42% 58%', gap: 16 }}>
        <div className="card" style={{ padding: 24 }}>
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>Algorithm Usage</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Observed encryption algorithms</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 18 }}>
            {algorithmRows.length > 0 ? algorithmRows.map((row) => (
              <div key={row.algorithm}>
                <div className="row-between">
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{row.algorithm}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>{row.count}</span>
                </div>
                <div style={{ width: '100%', height: 8, background: 'var(--bg-primary)', border: '1px solid var(--border-subtle)', marginTop: 6 }}>
                  <div style={{ width: `${row.width}%`, height: '100%', background: 'var(--accent-blue)' }} />
                </div>
              </div>
            )) : (
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                {loading ? 'Loading algorithm usage...' : 'No encryption activity recorded yet.'}
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', height: 52, borderBottom: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>Recent Events</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {activity.some((row) => row.source === 'audit') ? 'Admin audit feed' : 'Profile activity fallback'}
            </span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                {['ACTION', 'DETAILS', 'SOURCE', 'TIME'].map((heading) => <th key={heading}>{heading}</th>)}
              </tr>
            </thead>
            <tbody>
              {activity.length > 0 ? activity.map((row) => (
                <tr key={row.id}>
                  <td style={{ color: 'var(--accent-blue)', fontSize: 12, fontWeight: 500 }}>{humanizeAction(row.action)}</td>
                  <td><span className="truncate" style={{ display: 'block', maxWidth: 380 }}>{formatDetails(row.details)}</span></td>
                  <td style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{row.source}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>{formatRelativeTime(row.created_at)}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={4} style={{ color: 'var(--text-muted)' }}>
                    {loading ? 'Loading recent events...' : 'No recent analytics events yet.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
