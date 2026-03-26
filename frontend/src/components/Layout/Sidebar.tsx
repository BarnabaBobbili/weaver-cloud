import { Link, useLocation } from 'react-router-dom';
import { BarChart2, LayoutDashboard, Lock, ScrollText, Settings2, Shield, Timer, UserRound, Users } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';

export default function Sidebar() {
  const location = useLocation();
  const { user } = useAuth();

  const isActive = (path: string) => location.pathname === path || location.pathname.startsWith(`${path}/`);

  const commonItems = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/classify', label: 'Classify', icon: Lock },
    { path: '/history', label: 'History', icon: ScrollText },
    { path: '/shares', label: 'Shares', icon: Shield },
    { path: '/profile', label: 'Profile', icon: UserRound },
    { path: '/help', label: 'Help', icon: Settings2 },
  ];

  const analystItems = [
    { path: '/analytics', label: 'Analytics', icon: BarChart2 },
    { path: '/benchmarks', label: 'Benchmarks', icon: Timer },
  ];

  const adminItems = [
    { path: '/admin/users', label: 'Users', icon: Users },
    { path: '/admin/policies', label: 'Policies', icon: Shield },
    { path: '/audit-logs', label: 'Audit Logs', icon: ScrollText },
    { path: '/admin/shares', label: 'All Shares', icon: Shield },
    { path: '/admin/compliance', label: 'Compliance', icon: BarChart2 },
  ];

  const initials = user?.full_name
    ? user.full_name.split(' ').map((part) => part[0]).join('').slice(0, 2).toUpperCase()
    : 'U';

  return (
    <aside className="app-sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-name">WEAVER</div>
        <div className="sidebar-logo-sub">Cryptographic Policy Engine</div>
      </div>

      <nav className="sidebar-nav">
        {commonItems.map(({ path, label, icon: Icon }) => (
          <Link key={path} to={path} className={`nav-item ${isActive(path) ? 'active' : ''}`}>
            <Icon size={16} className="nav-icon" />
            <span className="nav-label">{label}</span>
          </Link>
        ))}

        {(user?.role === 'analyst' || user?.role === 'admin') && (
          <>
            <div className="nav-divider" />
            {analystItems.map(({ path, label, icon: Icon }) => (
              <Link key={path} to={path} className={`nav-item ${isActive(path) ? 'active' : ''}`}>
                <Icon size={16} className="nav-icon" />
                <span className="nav-label">{label}</span>
              </Link>
            ))}
          </>
        )}

        {user?.role === 'admin' && (
          <>
            <div className="nav-divider" />
            {adminItems.map(({ path, label, icon: Icon }) => (
              <Link key={path} to={path} className={`nav-item ${isActive(path) ? 'active' : ''}`}>
                <Icon size={16} className="nav-icon" />
                <span className="nav-label">{label}</span>
                <span className="nav-badge">Admin</span>
              </Link>
            ))}
          </>
        )}
      </nav>

      <div className="sidebar-user">
        <Link to="/profile" style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
          <div className="user-avatar">{initials}</div>
          <div className="user-info">
            <div className="user-name">{user?.full_name || 'User'}</div>
            <div className="user-role">{user?.role || 'viewer'}</div>
          </div>
        </Link>
      </div>
    </aside>
  );
}
