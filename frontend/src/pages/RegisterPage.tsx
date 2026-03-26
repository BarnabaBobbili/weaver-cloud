import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getApiErrorMessage } from '../utils/apiError';

function PwStrength({ pw }: { pw: string }) {
  const score = !pw ? 0 : pw.length < 6 ? 1 : pw.length < 8 ? 2 : /[A-Z]/.test(pw) && /\d/.test(pw) && /[^A-Za-z0-9]/.test(pw) ? 4 : 3;
  const labels = ['', 'Weak', 'Fair', 'Strong', 'Excellent'];
  const colors = ['', 'var(--accent-red)', 'var(--accent-amber)', 'var(--accent-green)', 'var(--accent-blue)'];
  return (
    <div style={{ marginTop: 6 }}>
      <div className="pw-strength-bar">
        <div className="pw-strength-fill" style={{ width: `${score * 25}%`, background: colors[score] }} />
      </div>
      {score > 0 && <div style={{ fontSize: 11, color: colors[score], marginTop: 3 }}>{labels[score]}</div>}
    </div>
  );
}

function AuthLeft() {
  return (
    <div style={{ maxWidth: 320, padding: '0 40px', position: 'relative', zIndex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <rect width="32" height="32" rx="8" fill="#2ca8fe" fillOpacity=".12"/>
          <rect width="32" height="32" rx="8" stroke="#2ca8fe" strokeOpacity=".3" strokeWidth="1"/>
          <path d="M8 24L16 8L24 24" stroke="#2ca8fe" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M11 18h10" stroke="#2ca8fe" strokeWidth="2" strokeLinecap="round"/>
        </svg>
        <span className="auth-logo-name">WEAV<span className="auth-logo-blue">ER</span></span>
      </div>
      <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 8 }}>
        AI-Driven Adaptive Cryptographic Policy Engine
      </div>
      <div className="auth-divider" />
      <div className="auth-feature-list">
        {[
          'Automatic classification of text and files',
          'AI-selected encryption — no manual choices',
          'Explainable AI rationale for every decision',
          'Secure, time-limited encrypted share links',
        ].map(feat => (
          <div key={feat} className="auth-feature-item">
            <div className="auth-feature-icon">
              <svg viewBox="0 0 10 10"><path d="M2 5l2 2 4-4" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </div>
            {feat}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 52 }}>
        <div className="auth-panel-caption">M.Tech Cyber Security · Semester 2 Project</div>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setError('Passwords do not match.'); return; }
    setError(''); setLoading(true);
    try { await register(email, password, fullName); navigate('/dashboard'); }
    catch (err: unknown) { setError(getApiErrorMessage(err, 'Registration failed.')); }
    finally { setLoading(false); }
  };

  return (
    <div className="split-layout">
      <div className="split-left"><AuthLeft /></div>
      <div className="split-right">
        <div className="auth-form-wrap">
          <h1 className="auth-title">Create Account</h1>
          <p className="auth-subtitle">Set up your Weaver identity in seconds.</p>

          {error && <div className="auth-error"><span>⚠</span>{error}</div>}

          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input className="form-input" type="text" placeholder="Jane Smith"
                value={fullName} onChange={e => setFullName(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input className="form-input" type="email" placeholder="you@example.com"
                value={email} onChange={e => setEmail(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input className="form-input" type="password" placeholder="Min 8 chars, mixed case + special"
                value={password} onChange={e => setPassword(e.target.value)} required minLength={8} />
              <PwStrength pw={password} />
            </div>
            <div className="form-group">
              <label className="form-label">Confirm Password</label>
              <input className="form-input" type="password" placeholder="••••••••"
                value={confirm} onChange={e => setConfirm(e.target.value)} required />
            </div>
            <button type="submit" className="btn btn-primary btn-full btn-lg" style={{ marginTop: 4 }} disabled={loading}>
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <p className="auth-footer-text">
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
