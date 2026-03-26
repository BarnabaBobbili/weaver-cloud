import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DEMO_AUTH_ENABLED, demoCredentials } from '../context/demoAuth';
import { getApiErrorMessage } from '../utils/apiError';

/* ── TOTP digit inputs ── */
function TOTPInputs({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const refs = useRef<HTMLInputElement[]>([]);
  const digits = Array.from({ length: 6 }, (_, i) => value[i] || '');

  const handleInput = (idx: number, next: string) => {
    if (!/^\d?$/.test(next)) return;
    const d = [...digits]; d[idx] = next; onChange(d.join(''));
    if (next && idx < 5) refs.current[idx + 1]?.focus();
  };
  const handleKeyDown = (idx: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !digits[idx] && idx > 0) refs.current[idx - 1]?.focus();
  };

  return (
    <div className="totp-inputs">
      {digits.map((d, i) => (
        <input
          key={i}
          ref={el => { if (el) refs.current[i] = el; }}
          className="totp-input"
          maxLength={1} value={d} type="text" inputMode="numeric"
          onChange={e => handleInput(i, e.target.value)}
          onKeyDown={e => handleKeyDown(i, e)}
        />
      ))}
    </div>
  );
}

/* ── Left panel content ── */
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
          'Classify data sensitivity with ML',
          'Adaptive encryption — AI selects the cipher',
          'Explainable AI decisions on every operation',
          'Secure share links with expiry & limits',
        ].map(feat => (
          <div key={feat} className="auth-feature-item">
            <div className="auth-feature-icon">
              <svg viewBox="0 0 10 10"><path d="M2 5l2 2 4-4" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </div>
            {feat}
          </div>
        ))}
      </div>

      <div style={{ position: 'absolute', bottom: -200, left: 40 }}>
        <div className="auth-panel-caption">M.Tech Cyber Security · Semester 2 Project</div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, loginMfa } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [mfaStep, setMfaStep] = useState(false);
  const [tempToken, setTempToken] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [useRecovery, setUseRecovery] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setLoading(true);
    try {
      const result = await login(email, password);
      if (result.mfa_required) { setTempToken(result.temp_token || ''); setMfaStep(true); setMfaCode(''); }
      else navigate('/dashboard');
    } catch (err: unknown) { setError(getApiErrorMessage(err, 'Invalid credentials')); }
    finally { setLoading(false); }
  };

  const handleMfa = async () => {
    if (mfaCode.length !== 6) { setError('Enter the 6-digit code.'); return; }
    setError(''); setLoading(true);
    try { await loginMfa(mfaCode, tempToken); navigate('/dashboard'); }
    catch (err) { setError(getApiErrorMessage(err, 'Invalid TOTP code.')); }
    finally { setLoading(false); }
  };

  const handleRecovery = async () => {
    if (!email.trim() || !recoveryCode.trim()) { setError('Enter email and recovery code.'); return; }
    setError(''); setLoading(true);
    try {
      const r = await client.post('/api/auth/login/recovery', { email, password, recovery_code: recoveryCode });
      localStorage.setItem('access_token', (r.data as { access_token: string }).access_token);
      window.location.href = '/dashboard';
    } catch (err) { setError(getApiErrorMessage(err, 'Recovery login failed.')); }
    finally { setLoading(false); }
  };

  return (
    <div className="split-layout">
      <div className="split-left"><AuthLeft /></div>
      <div className="split-right">
        <div className="auth-form-wrap">
          {!mfaStep ? (
            <>
              <h1 className="auth-title">Sign in</h1>
              <p className="auth-subtitle">Enter your credentials to continue.</p>

              {error && <div className="auth-error"><span>⚠</span>{error}</div>}

              {DEMO_AUTH_ENABLED && (
                <div className="demo-box">
                  <div className="demo-box-label">Demo credentials</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {demoCredentials.map(c => (
                      <button
                        key={c.email}
                        type="button"
                        className="btn btn-ghost btn-sm"
                        style={{ justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11 }}
                        onClick={() => { setEmail(c.email); setPassword(c.password); setError(''); }}
                      >
                        <span style={{ textTransform: 'capitalize', fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 12 }}>{c.role}</span>
                        <span style={{ color: 'var(--text-muted)' }}>{c.email}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <form onSubmit={handleLogin} className="auth-form">
                <div className="form-group">
                  <label className="form-label">Email</label>
                  <input className="form-input" type="email" placeholder="you@example.com"
                    value={email} onChange={e => setEmail(e.target.value)} required />
                </div>
                <div className="form-group">
                  <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Password</span>
                    <span style={{ color: 'var(--accent-blue)', cursor: 'pointer', fontWeight: 400, letterSpacing: 0, textTransform: 'none', fontSize: 12 }}>Forgot?</span>
                  </label>
                  <input className="form-input" type="password" placeholder="••••••••"
                    value={password} onChange={e => setPassword(e.target.value)} required />
                </div>
                <button type="submit" className="btn btn-primary btn-full btn-lg" disabled={loading}>
                  {loading ? 'Signing in…' : 'Sign In'}
                </button>
              </form>

              <p className="auth-footer-text">
                Don&apos;t have an account? <Link to="/register">Create one</Link>
              </p>
            </>
          ) : (
            <>
              <h1 className="auth-title">{useRecovery ? 'Recovery Code' : 'Two-Factor Auth'}</h1>
              <p className="auth-subtitle">
                {useRecovery ? 'Enter one of your backup recovery codes.' : 'Enter the 6-digit code from your authenticator app.'}
              </p>

              {error && <div className="auth-error"><span>⚠</span>{error}</div>}

              {!useRecovery ? (
                <>
                  <div style={{ marginTop: 28 }}><TOTPInputs value={mfaCode} onChange={setMfaCode} /></div>
                  <button className="btn btn-primary btn-full btn-lg" style={{ marginTop: 24 }}
                    disabled={loading || mfaCode.length !== 6} onClick={() => void handleMfa()}>
                    {loading ? 'Verifying…' : 'Verify'}
                  </button>
                </>
              ) : (
                <>
                  <div className="form-group" style={{ marginTop: 24 }}>
                    <label className="form-label">Recovery Code</label>
                    <input className="form-input" placeholder="XXXX-XXXX"
                      value={recoveryCode} onChange={e => setRecoveryCode(e.target.value)} />
                  </div>
                  <button className="btn btn-primary btn-full btn-lg" style={{ marginTop: 24 }}
                    disabled={loading || !recoveryCode.trim()} onClick={() => void handleRecovery()}>
                    {loading ? 'Verifying…' : 'Sign In with Recovery Code'}
                  </button>
                </>
              )}

              <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center' }}>
                <button className="link-blue" onClick={() => { setUseRecovery(v => !v); setError(''); }}>
                  {useRecovery ? 'Use authenticator app' : 'Use a recovery code'}
                </button>
                <button className="link-muted" onClick={() => { setMfaStep(false); setMfaCode(''); setRecoveryCode(''); setError(''); }}>
                  ← Back to sign in
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
