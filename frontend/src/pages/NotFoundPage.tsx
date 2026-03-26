import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div style={{
      minHeight: '100vh', background: 'var(--bg-primary)',
      display: 'flex', alignItems: 'center', justifyContent: 'center'
    }}>
      <div style={{ textAlign: 'center', maxWidth: 400 }}>
        <div style={{ fontSize: 14, fontWeight: 500, letterSpacing: 3, color: 'var(--text-muted)' }}>WEAVER</div>
        <div style={{ fontSize: 72, fontWeight: 500, color: 'var(--text-primary)', marginTop: 32, letterSpacing: -2 }}>404</div>
        <div style={{ fontSize: 16, color: 'var(--text-muted)', marginTop: 12 }}>Page not found</div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 8, maxWidth: 320, margin: '8px auto 0' }}>
          The page you're looking for doesn't exist or has been moved.
        </div>
        <div style={{ marginTop: 32, display: 'flex', gap: 12, justifyContent: 'center' }}>
          <Link to="/dashboard" className="btn btn-primary" style={{ width: 160, height: 42, fontSize: 14, justifyContent: 'center' }}>
            Go to Dashboard
          </Link>
          <Link to="/" className="btn btn-ghost" style={{ width: 160, height: 42, fontSize: 14, justifyContent: 'center' }}>
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}
