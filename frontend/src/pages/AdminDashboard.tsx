import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminApi, analyticsApi } from '../api';
import { ChartCard, SensitivityPieChart, ActivityBarChart } from '../components/DashboardCharts';
import type {
  AdminHealth, AdminSecurityAlerts, AdminUserSummary,
  AnalyticsOverview, AuditLog, ComplianceReport, SensitivityDistribution,
} from '../types';
import { formatRelativeTime, humanizeAction } from '../utils/formatters';

interface AdminDashboardData {
  total_classifications: number;
  classifications_this_week: number;
  total_encryptions: number;
  encryptions_this_week: number;
  total_users?: number;
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
  ml_model_source?: string;
}

const EMPTY_OVERVIEW: AnalyticsOverview = {
  total_classifications: 0, total_encryptions: 0, active_shares: 0, total_users: 0,
  classifications_this_week: 0, encryptions_this_week: 0, expiring_shares: 0,
  classifications_this_month: 0, avg_confidence: null, most_common_level: null, most_common_pct: 0,
};
const EMPTY_DIST: SensitivityDistribution = { public: 0, internal: 0, confidential: 0, highly_sensitive: 0 };
const LEVEL_COLOR: Record<keyof SensitivityDistribution, string> = {
  public: 'var(--accent-green)', internal: 'var(--accent-blue)',
  confidential: 'var(--accent-amber)', highly_sensitive: 'var(--accent-red)',
};

export default function AdminDashboard() {
  const [overview, setOverview] = useState<AnalyticsOverview>(EMPTY_OVERVIEW);
  const [health, setHealth] = useState<AdminHealth | null>(null);
  const [summary, setSummary] = useState<AdminUserSummary | null>(null);
  const [alerts, setAlerts] = useState<AdminSecurityAlerts | null>(null);
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [distribution, setDistribution] = useState<SensitivityDistribution>(EMPTY_DIST);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [exportingAudit, setExportingAudit] = useState(false);
  const [adminDashboardData, setAdminDashboardData] = useState<AdminDashboardData | null>(null);

  useEffect(() => {
    analyticsApi.overview().then(r => setOverview(r.data)).catch(() => {});
    analyticsApi.adminHealth().then(r => setHealth(r.data)).catch(() => {});
    analyticsApi.adminUserSummary().then(r => setSummary(r.data)).catch(() => {});
    analyticsApi.adminSecurityAlerts().then(r => setAlerts(r.data)).catch(() => {});
    analyticsApi.sensitivityDistribution('30D').then(r => setDistribution(r.data)).catch(() => {});
    adminApi.complianceReport().then(r => setReport(r.data)).catch(() => {});
    adminApi.adminAuditLogs({ page: 1, limit: 5 }).then(r => setLogs(r.data.items)).catch(() => {});
    // Fetch unified dashboard data (role-based, includes admin data)
    analyticsApi.dashboard().then(r => setAdminDashboardData(r.data)).catch(() => {});
  }, []);

  const distRows = useMemo(() => {
    const total = Object.values(distribution).reduce((s, v) => s + v, 0);
    return (Object.entries(distribution) as Array<[keyof SensitivityDistribution, number]>).map(([level, count]) => ({
      level, count, pct: total ? Math.round((count / total) * 100) : 0, color: LEVEL_COLOR[level],
    }));
  }, [distribution]);

  const uptime = health?.uptime || health?.uptime_human || (health?.uptime_seconds !== undefined ? `${health.uptime_seconds}s` : 'n/a');
  const memory = health?.memory || (health?.memory_mb !== undefined && health.memory_mb !== null ? `${health.memory_mb} MB` : 'n/a');
  const registrations = summary?.registrations_last_30_days ?? summary?.new_registrations_30d ?? summary?.new_registrations ?? 0;
  const expiringShares = alerts?.expiring_shares ?? alerts?.expiring_shares_24h ?? 0;

  const handleExportAudit = async () => {
    setExportingAudit(true);
    try {
      const response = await adminApi.exportAuditLogs();
      const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = 'weaver-audit-logs.csv'; a.click();
      URL.revokeObjectURL(url);
    } catch { /* silent */ }
    finally { setExportingAudit(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: -0.3 }}>Admin Dashboard</h2>
            <span className="admin-badge">⚡ Elevated</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            System-wide overview · full access
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link to="/admin/users" className="btn btn-ghost btn-sm">Manage Users</Link>
          <button className="btn btn-outline btn-sm" onClick={() => void handleExportAudit()} disabled={exportingAudit}>
            {exportingAudit ? 'Exporting…' : '↓ Export Audit'}
          </button>
        </div>
      </div>

      {/* System-wide stats */}
      <div className="grid-4">
        {[
          { label: 'Total Users',     val: overview.total_users,          icon: '👥', color: 'var(--accent-blue)'   },
          { label: 'Classifications', val: overview.total_classifications, icon: '🔍', color: 'var(--accent-green)'  },
          { label: 'Encryptions',     val: overview.total_encryptions,    icon: '🔐', color: 'var(--accent-amber)'  },
          { label: 'Active Shares',   val: overview.active_shares,        icon: '📡', color: 'var(--accent-red)'    },
        ].map(s => (
          <div key={s.label} className="stat-block">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ fontSize: 18 }}>{s.icon}</div>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: s.color }} />
            </div>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value">{Number(s.val).toLocaleString()}</div>
          </div>
        ))}
      </div>

      {/* Charts Row - Activity and Distribution */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <ChartCard title="System Activity (Last 7 Days)" subtitle="All users combined">
          <ActivityBarChart data={adminDashboardData?.daily_activity || []} />
        </ChartCard>
        <ChartCard title="Classification Distribution" subtitle="System-wide breakdown">
          <SensitivityPieChart data={adminDashboardData?.sensitivity_distribution || { public: 0, internal: 0, confidential: 0, highly_sensitive: 0 }} />
        </ChartCard>
      </div>

      {/* ML Model Status Banner */}
      {adminDashboardData?.ml_model_source && (
        <div style={{ 
          padding: '12px 16px', 
          background: adminDashboardData.ml_model_source === 'cloud_trained' 
            ? 'linear-gradient(90deg, rgba(34,197,94,0.1) 0%, rgba(59,130,246,0.1) 100%)' 
            : 'rgba(245,158,11,0.1)',
          borderRadius: 8,
          border: `1px solid ${adminDashboardData.ml_model_source === 'cloud_trained' ? 'rgba(34,197,94,0.3)' : 'rgba(245,158,11,0.3)'}`,
          display: 'flex',
          alignItems: 'center',
          gap: 12
        }}>
          <span style={{ fontSize: 20 }}>
            {adminDashboardData.ml_model_source === 'cloud_trained' ? '☁️' : '💻'}
          </span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              ML Model: {adminDashboardData.ml_model_source === 'cloud_trained' ? 'Azure ML Cloud-Trained' : 'Local Model'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {adminDashboardData.ml_model_source === 'cloud_trained' 
                ? 'Using TF-IDF classifier trained in Azure Machine Learning' 
                : 'Using local fallback model'}
            </div>
          </div>
        </div>
      )}

      {/* System health + user summary + security alerts (3-col) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>

        <div className="dash-card">
          <div className="dash-card-title">System Health</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 16 }}>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Uptime</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--accent-green)' }}>{uptime}</span>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Memory</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{memory}</span>
            </div>
            {Object.entries(health?.db_records || {}).map(([k, v]) => (
              <div key={k} className="row-between">
                <span style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'capitalize' }}>{k}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-title">User Summary</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 16 }}>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>New registrations (30d)</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--accent-blue)' }}>{registrations}</span>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Locked accounts</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: (summary?.locked_accounts ?? 0) > 0 ? 'var(--accent-amber)' : 'var(--text-primary)' }}>
                {summary?.locked_accounts ?? 0}
              </span>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>MFA adoption</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: (summary?.mfa_adoption_pct ?? 0) > 70 ? 'var(--accent-green)' : 'var(--accent-amber)' }}>
                {summary?.mfa_adoption_pct ?? 0}%
              </span>
            </div>
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-title">Security Alerts</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 16 }}>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Failed logins (24h)</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: (alerts?.failed_logins_24h ?? 0) > 5 ? 'var(--accent-red)' : 'var(--text-primary)' }}>
                {alerts?.failed_logins_24h ?? 0}
              </span>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Locked accounts</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{alerts?.locked_accounts ?? 0}</span>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Expiring shares (24h)</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: expiringShares > 0 ? 'var(--accent-amber)' : 'var(--text-primary)' }}>
                {expiringShares}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Quick admin actions */}
      <div className="dash-card">
        <div className="dash-card-title">Admin Actions</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8, marginTop: 16 }}>
          {[
            { label: 'Manage Users',    href: '/admin/users',      desc: 'View, edit and lock accounts', icon: '👥', bg: 'rgba(44,168,254,.12)'  },
            { label: 'Policies',        href: '/admin/policies',   desc: 'Crypto policy overrides',       icon: '📜', bg: 'rgba(69,65,241,.12)'   },
            { label: 'All Shares',      href: '/admin/shares',     desc: 'Monitor all share links',       icon: '🔗', bg: 'rgba(76,175,121,.12)'  },
            { label: 'Compliance',      href: '/admin/compliance', desc: 'Generate compliance reports',   icon: '📊', bg: 'rgba(230,168,23,.12)'  },
            { label: 'Audit Logs',      href: '/audit-logs',       desc: 'Search system event logs',      icon: '🗂', bg: 'rgba(224,85,85,.12)'   },
          ].map(a => (
            <Link key={a.label} to={a.href} className="quick-action">
              <div className="quick-action-icon" style={{ background: a.bg }}>{a.icon}</div>
              <div className="quick-action-body">
                <div className="quick-action-title">{a.label}</div>
                <div className="quick-action-desc">{a.desc}</div>
              </div>
            </Link>
          ))}
          <button className="quick-action" onClick={() => void handleExportAudit()} disabled={exportingAudit}>
            <div className="quick-action-icon" style={{ background: 'rgba(100,100,100,.12)' }}>↓</div>
            <div className="quick-action-body">
              <div className="quick-action-title">{exportingAudit ? 'Exporting…' : 'Export Audit'}</div>
              <div className="quick-action-desc">Download audit CSV</div>
            </div>
          </button>
        </div>
      </div>

      {/* Distribution + compliance + audit */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>

        <div className="dash-card">
          <div className="dash-card-title">Sensitivity Distribution</div>
          <div className="dash-card-sub">System-wide · last 30 days</div>
          <div className="stacked-bar" style={{ marginTop: 16 }}>
            {distRows.map(r => (
              <div key={r.level} className="stacked-bar-seg" style={{ width: `${r.pct || 1}%`, background: r.color, opacity: r.pct ? 1 : 0.15 }} />
            ))}
          </div>
          <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {distRows.map(r => (
              <div key={r.level} className="row-between">
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 8, height: 8, background: r.color, borderRadius: 2 }} />
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{r.level.replace('_',' ')}</span>
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{r.count} / {r.pct}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-title">Compliance Snapshot</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Security Score</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: (report?.security_score ?? 0) >= 80 ? 'var(--accent-green)' : 'var(--accent-amber)', letterSpacing: -0.5 }}>
                {report?.security_score ?? 0}
              </div>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Policy violations</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: (report?.policy_violations ?? 0) > 0 ? 'var(--accent-amber)' : 'var(--accent-green)' }}>
                {report?.policy_violations ?? 0}
              </span>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Unencrypted ops</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{report?.unencrypted_ops ?? 0}</span>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>MFA adoption</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{report?.mfa_adoption_pct ?? 0}%</span>
            </div>
          </div>
        </div>

        <div className="dash-card">
          <div className="dash-card-title">Recent Audit Activity</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
            {logs.length > 0 ? logs.map(item => (
              <div key={item.id} className="timeline-item">
                <div className="timeline-dot" style={{ background: 'var(--accent-purple)' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.4 }}>{humanizeAction(item.action)}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{formatRelativeTime(item.created_at)}</div>
                </div>
              </div>
            )) : (
              <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '20px 0', textAlign: 'center' }}>No audit activity.</div>
            )}
          </div>
          {logs.length > 0 && (
            <Link to="/audit-logs" style={{ display: 'block', marginTop: 16, fontSize: 12, color: 'var(--accent-blue)', textAlign: 'center' }}>
              View all logs →
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
