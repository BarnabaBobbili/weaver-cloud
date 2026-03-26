import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import AppLayout from './components/Layout/AppLayout';
import { useAuth } from './context/AuthContext';
import type { UserRole } from './types';

// Public pages
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DecryptPage from './pages/DecryptPage';
import NotFoundPage from './pages/NotFoundPage';

// Authenticated pages
import DashboardPage from './pages/DashboardPage';
import ClassifyPage from './pages/ClassifyPage';
import HistoryPage from './pages/HistoryPage';
import SharesPage from './pages/SharesPage';
import AnalyticsPage from './pages/AnalyticsPage';
import AuditLogsPage from './pages/AuditLogsPage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminPoliciesPage from './pages/AdminPoliciesPage';
import AdminSharesPage from './pages/AdminSharesPage';
import AdminCompliancePage from './pages/AdminCompliancePage';
import BenchmarkPage from './pages/BenchmarkPage';
import MFASetupPage from './pages/MFASetupPage';
import ProfilePage from './pages/ProfilePage';
import HelpPage from './pages/HelpPage';

function RoleRoute({
  allowedRoles,
  children,
}: {
  allowedRoles: UserRole[];
  children: ReactNode;
}) {
  const { user, loading } = useAuth();

  if (loading) {
    return null;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/decrypt/:token" element={<DecryptPage />} />
          <Route path="/404" element={<NotFoundPage />} />

          {/* Authenticated routes */}
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/classify" element={<ClassifyPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/shares" element={<SharesPage />} />
            <Route
              path="/analytics"
              element={(
                <RoleRoute allowedRoles={['analyst', 'admin']}>
                  <AnalyticsPage />
                </RoleRoute>
              )}
            />
            <Route
              path="/audit-logs"
              element={(
                <RoleRoute allowedRoles={['admin']}>
                  <AuditLogsPage />
                </RoleRoute>
              )}
            />
            <Route
              path="/admin/users"
              element={(
                <RoleRoute allowedRoles={['admin']}>
                  <AdminUsersPage />
                </RoleRoute>
              )}
            />
            <Route
              path="/admin/policies"
              element={(
                <RoleRoute allowedRoles={['admin']}>
                  <AdminPoliciesPage />
                </RoleRoute>
              )}
            />
            <Route
              path="/admin/shares"
              element={(
                <RoleRoute allowedRoles={['admin']}>
                  <AdminSharesPage />
                </RoleRoute>
              )}
            />
            <Route
              path="/admin/compliance"
              element={(
                <RoleRoute allowedRoles={['admin']}>
                  <AdminCompliancePage />
                </RoleRoute>
              )}
            />
            <Route
              path="/benchmarks"
              element={(
                <RoleRoute allowedRoles={['analyst', 'admin']}>
                  <BenchmarkPage />
                </RoleRoute>
              )}
            />
            <Route path="/mfa-setup" element={<MFASetupPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/help" element={<HelpPage />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
