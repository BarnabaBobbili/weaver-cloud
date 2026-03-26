import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { classifyApi, profileApi } from '../api';
import { useAuth } from '../context/AuthContext';
import type { ClassificationRecord, ProfileActivityItem, ProfileStats } from '../types';
import { formatRelativeTime, humanizeAction } from '../utils/formatters';

const LEVELS = ['public', 'internal', 'confidential', 'highly_sensitive'] as const;
const LEVEL_COLOR: Record<string, string> = {
  public:           'var(--accent-green)',
  internal:         'var(--accent-blue)',
  confidential:     'var(--accent-amber)',
  highly_sensitive: 'var(--accent-red)',
};
const LEVEL_LABEL: Record<string, string> = {
  public: 'Public', internal: 'Internal', confidential: 'Confidential', highly_sensitive: 'Sensitive',
};

const EMPTY_STATS: ProfileStats = { total_classifications: 0, total_encryptions: 0, total_shares: 0, active_shares: 0 };

export default function UserDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<ProfileStats>(EMPTY_STATS);
  const [activity, setActivity] = useState<ProfileActivityItem[]>([]);
  const [historyRows, setHistoryRows] = useState<ClassificationRecord[]>([]);

  useEffect(() => {
    profileApi.stats().then(r => setStats(r.data)).catch(() => {});
    profileApi.activity(1).then(r => setActivity(r.data.items.slice(0, 6))).catch(() => {});
    classifyApi.history({ page: 1, limit: 50 }).then(r => setHistoryRows(r.data.items)).catch(() => {});
  }, []);

  const distribution = useMemo(() => {
    const counts = { public: 0, internal: 0, confidential: 0, highly_sensitive: 0 };
    historyRows.forEach(r => { counts[r.predicted_level] += 1; });
    const total = historyRows.length || 1;
    return LEVELS.map(level => ({ level, count: counts[level], pct: Math.round((counts[level] / total) * 100) }));
  }, [historyRows]);

  const secScore = (user?.mfa_enabled ? 70 : 40) + (stats.active_shares === 0 ? 20 : 10) + (stats.total_encryptions > 0 ? 10 : 0);
  const scoreColor = secScore >= 80 ? 'var(--accent-green)' : secScore >= 60 ? 'var(--accent-amber)' : 'var(--accent-red)';
  const initials = user?.full_name?.split(' ').map(n => n[0]).join('').slice(0,2).toUpperCase() ?? '?';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Greeting */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: -0.3 }}>
            Welcome back, {user?.full_name?.split(' ')[0] ?? 'there'} 👋
          </h2>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            {user?.email} · {user?.role ?? 'user'}
          </div>
        </div>
        <Link to="/classify" className="btn btn-primary">
          + Classify
        </Link>
      </div>

      {/* Stat blocks */}
      <div className="grid-4">
        {[
          { label: 'Classifications',  val: stats.total_classifications,  icon: '🔍' },
          { label: 'Encryptions',      val: stats.total_encryptions,      icon: '🔐' },
          { label: 'Total Shares',     val: stats.total_shares,           icon: '🔗' },
          { label: 'Active Shares',    val: stats.active_shares,          icon: '📡' },
        ].map(s => (
          <div key={s.label} className="stat-block">
            <div style={{ fontSize: 18, marginBottom: 8 }}>{s.icon}</div>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value">{Number(s.val).toLocaleString()}</div>
          </div>
        ))}
      </div>

      {/* Middle row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 16 }}>

        {/* Distribution */}
        <div className="dash-card">
          <div className="dash-card-title">Classification Distribution</div>
          <div className="dash-card-sub">Across your last 50 operations</div>
          <div className="stacked-bar" style={{ marginTop: 20 }}>
            {distribution.map(({ level, pct }) => (
              <div key={level} className="stacked-bar-seg" style={{ width: `${pct || 1}%`, background: LEVEL_COLOR[level], opacity: pct ? 1 : 0.15 }} />
            ))}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 16 }}>
            {distribution.map(({ level, count, pct }) => (
              <div key={level} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 8, height: 8, background: LEVEL_COLOR[level], borderRadius: 2, flexShrink: 0 }} />
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{LEVEL_LABEL[level]}</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginLeft: 'auto' }}>{count} / {pct}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Security status */}
        <div className="dash-card">
          <div className="dash-card-title">Security Status</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginTop: 20 }}>
            <div className="score-ring" style={{ background: `${scoreColor}18`, border: `2px solid ${scoreColor}40` }}>
              <span style={{ color: scoreColor, fontSize: 22, fontWeight: 700 }}>{secScore}</span>
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                {secScore >= 80 ? 'Excellent' : secScore >= 60 ? 'Good' : 'Needs attention'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Security score</div>
            </div>
          </div>
          <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>MFA</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: user?.mfa_enabled ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                {user?.mfa_enabled ? '✓ Enabled' : '✗ Disabled'}
              </span>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Active shares</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{stats.active_shares}</span>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Encryptions</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)' }}>{stats.total_encryptions}</span>
            </div>
          </div>
          {!user?.mfa_enabled && (
            <Link to="/mfa-setup" className="btn btn-outline btn-sm" style={{ marginTop: 16, width: '100%', justifyContent: 'center' }}>
              Enable MFA →
            </Link>
          )}
        </div>
      </div>

      {/* Bottom row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Quick actions */}
        <div className="dash-card">
          <div className="dash-card-title">Quick Actions</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 16 }}>
            {[
              { label: 'Classify',   href: '/classify', desc: 'Analyze and classify new data',    icon: '🔍', bg: 'rgba(44,168,254,.12)'  },
              { label: 'My Shares',  href: '/shares',   desc: 'Review active & expired links',   icon: '🔗', bg: 'rgba(69,65,241,.12)'   },
              { label: 'History',    href: '/history',  desc: 'Search recent classifications',   icon: '📋', bg: 'rgba(76,175,121,.12)'  },
            ].map(a => (
              <Link key={a.label} to={a.href} className="quick-action">
                <div className="quick-action-icon" style={{ background: a.bg }}>{a.icon}</div>
                <div className="quick-action-body">
                  <div className="quick-action-title">{a.label}</div>
                  <div className="quick-action-desc">{a.desc}</div>
                </div>
                <div className="quick-action-arrow">›</div>
              </Link>
            ))}
          </div>
        </div>

        {/* Recent activity */}
        <div className="dash-card">
          <div className="dash-card-title">Recent Activity</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 16 }}>
            {activity.length > 0 ? activity.map(item => (
              <div key={item.id} className="timeline-item">
                <div className="timeline-dot" style={{ background: 'var(--accent-blue)' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.4 }}>{humanizeAction(item.action)}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{formatRelativeTime(item.created_at)}</div>
                </div>
              </div>
            )) : (
              <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '20px 0', textAlign: 'center' }}>
                No activity yet. <Link to="/classify" style={{ color: 'var(--accent-blue)' }}>Classify something</Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
