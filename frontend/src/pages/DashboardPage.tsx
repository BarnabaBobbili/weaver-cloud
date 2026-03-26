import { useAuth } from '../context/AuthContext';
import AdminDashboard from './AdminDashboard';
import UserDashboard from './UserDashboard';

export default function DashboardPage() {
  const { user } = useAuth();
  return user?.role === 'admin' ? <AdminDashboard /> : <UserDashboard />;
}
