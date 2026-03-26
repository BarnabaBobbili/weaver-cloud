import { useAuth } from '../../context/AuthContext';
import { useLocation } from 'react-router-dom';
import NotificationBell from '../NotificationBell';

const PAGE_TITLES: Record<string, { title: string; breadcrumb: string }> = {
  '/dashboard': { title: 'Dashboard', breadcrumb: 'Home / Dashboard' },
  '/classify': { title: 'Classify & Encrypt', breadcrumb: 'Dashboard / Classify & Encrypt' },
  '/history': { title: 'Classification History', breadcrumb: 'Dashboard / History' },
  '/shares': { title: 'Share Management', breadcrumb: 'Dashboard / Shares' },
  '/admin/shares': { title: 'All Shares', breadcrumb: 'Admin / Shares' },
  '/admin/compliance': { title: 'Compliance', breadcrumb: 'Admin / Compliance' },
  '/analytics': { title: 'Analytics', breadcrumb: 'Dashboard / Analytics' },
  '/audit-logs': { title: 'Audit Logs', breadcrumb: 'Dashboard / Audit Logs' },
  '/admin/users': { title: 'User Management', breadcrumb: 'Admin / Users' },
  '/admin/policies': { title: 'Crypto Policies', breadcrumb: 'Admin / Policies' },
  '/benchmarks': { title: 'Benchmarks', breadcrumb: 'Dashboard / Benchmarks' },
  '/mfa-setup': { title: 'MFA Setup', breadcrumb: 'Profile / MFA Setup' },
  '/profile': { title: 'Profile & Settings', breadcrumb: 'Account / Profile' },
  '/help': { title: 'Documentation', breadcrumb: 'Help / Documentation' },
};

export default function Header() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const info = PAGE_TITLES[location.pathname] || { title: 'Weaver', breadcrumb: '' };

  return (
    <header className="app-header">
      <div className="header-left">
        <div className="header-title">{info.title}</div>
        {info.breadcrumb && <div className="header-breadcrumb">{info.breadcrumb}</div>}
      </div>
      <div className="header-right">
        <span className={`mfa-badge ${user?.mfa_enabled ? 'active' : 'inactive'}`}>
          {user?.mfa_enabled ? 'MFA: Active' : 'MFA: Off'}
        </span>
        <NotificationBell />
        <button className="header-logout" onClick={logout}>Log out</button>
      </div>
    </header>
  );
}
