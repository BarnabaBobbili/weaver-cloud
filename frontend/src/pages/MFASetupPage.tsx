import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { authApi } from '../api';
import client from '../api/client';
import { getApiErrorMessage } from '../utils/apiError';

function TOTPInputs({ value, onChange }: { value: string; onChange: (code: string) => void }) {
  const refs = useRef<HTMLInputElement[]>([]);
  const digits = Array.from({ length: 6 }, (_, index) => value[index] || '');

  const handleInput = (index: number, nextValue: string) => {
    if (!/^\d?$/.test(nextValue)) {
      return;
    }
    const nextDigits = [...digits];
    nextDigits[index] = nextValue;
    onChange(nextDigits.join(''));
    if (nextValue && index < 5) {
      refs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Backspace' && !digits[index] && index > 0) {
      refs.current[index - 1]?.focus();
    }
  };

  return (
    <div className="totp-inputs">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(element) => {
            if (element) {
              refs.current[index] = element;
            }
          }}
          className="totp-input"
          maxLength={1}
          value={digit}
          onChange={(event) => handleInput(index, event.target.value)}
          onKeyDown={(event) => handleKeyDown(index, event)}
          type="text"
          inputMode="numeric"
        />
      ))}
    </div>
  );
}

function downloadRecoveryCodes(codes: string[]) {
  const blob = new Blob([codes.join('\n')], { type: 'text/plain;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'weaver-recovery-codes.txt';
  anchor.click();
  URL.revokeObjectURL(url);
}

function parseRecoveryCodes(payload: unknown): string[] {
  if (Array.isArray(payload)) {
    return payload.filter((item): item is string => typeof item === 'string');
  }
  if (payload && typeof payload === 'object') {
    const data = payload as { recovery_codes?: unknown; codes?: unknown };
    if (Array.isArray(data.recovery_codes)) {
      return data.recovery_codes.filter((item): item is string => typeof item === 'string');
    }
    if (Array.isArray(data.codes)) {
      return data.codes.filter((item): item is string => typeof item === 'string');
    }
  }
  return [];
}

export default function MFASetupPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [secret, setSecret] = useState('');
  const [qrData, setQrData] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [recoveryStatus, setRecoveryStatus] = useState('');

  const handleSetup = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await authApi.mfaSetup();
      setSecret(response.data.secret);
      setQrData(response.data.qr_data);
      setStep(2);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not generate an MFA secret.'));
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (totpCode.length !== 6) {
      setError('Enter the 6-digit code from your authenticator app.');
      return;
    }

    setError('');
    setLoading(true);
    try {
      await authApi.mfaVerify(totpCode);

      try {
        const response = await client.post('/api/auth/mfa/recovery-codes');
        const codes = parseRecoveryCodes(response.data);
        setRecoveryCodes(codes);
        setRecoveryStatus(
          codes.length > 0
            ? 'Save these one-time recovery codes now. They will not be shown again.'
            : 'MFA was enabled, but the backend did not return recovery codes.',
        );
      } catch {
        setRecoveryCodes([]);
        setRecoveryStatus('MFA was enabled, but the backend did not return recovery codes.');
      }

      setStep(3);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Invalid code. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  const Steps = () => (
    <div className="steps-row" style={{ marginBottom: 32 }}>
      {[{ n: 1, label: 'Generate Secret' }, { n: 2, label: 'Scan and Verify' }, { n: 3, label: 'Recovery Codes' }].map((item, index) => (
        <div key={item.n} style={{ display: 'flex', alignItems: 'center' }}>
          <div className="step-item">
            <div className={`step-circle ${step >= item.n ? 'done' : ''}`}>{item.n}</div>
            <div className={`step-label ${step === item.n ? 'active' : ''}`}>{item.label}</div>
          </div>
          {index < 2 && <div className="step-connector" />}
        </div>
      ))}
    </div>
  );

  if (step === 3) {
    return (
      <div style={{ maxWidth: 640, margin: '0 auto' }}>
        <Steps />
        <div className="card" style={{ padding: 32 }}>
          <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>MFA Enabled Successfully</div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.6 }}>
            {recoveryStatus || 'Your account now requires a TOTP code on login.'}
          </p>

          {recoveryCodes.length > 0 ? (
            <>
              <div
                style={{
                  marginTop: 24,
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                  gap: 12,
                }}
              >
                {recoveryCodes.map((code) => (
                  <div
                    key={code}
                    style={{
                      padding: '12px 14px',
                      border: '1px solid var(--border-subtle)',
                      background: 'var(--bg-primary)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 13,
                      color: 'var(--text-primary)',
                    }}
                  >
                    {code}
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 10, marginTop: 20, flexWrap: 'wrap' }}>
                <button className="btn btn-outline btn-sm" onClick={() => downloadRecoveryCodes(recoveryCodes)}>
                  Download Codes
                </button>
                <button className="btn btn-outline btn-sm" onClick={() => void navigator.clipboard.writeText(recoveryCodes.join('\n'))}>
                  Copy Codes
                </button>
              </div>
            </>
          ) : (
            <div
              style={{
                marginTop: 20,
                padding: 14,
                border: '1px solid var(--accent-amber)',
                background: 'rgba(212,145,75,0.12)',
                color: 'var(--accent-amber)',
                fontSize: 12,
                lineHeight: 1.6,
              }}
            >
              Recovery-code generation is not available on the current backend response.
            </div>
          )}

          <button className="btn btn-primary" style={{ marginTop: 24, width: 180 }} onClick={() => navigate('/profile')}>
            Back to Profile
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 520, margin: '0 auto' }}>
      <Steps />
      {step === 1 && (
        <div className="card" style={{ padding: 32 }}>
          <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>Set Up Two-Factor Authentication</div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 8 }}>
            Protect your account by requiring a TOTP code on every login.
          </p>
          {error && <div style={{ marginTop: 16, fontSize: 13, color: 'var(--accent-red)' }}>{error}</div>}
          <button className="btn btn-primary btn-full btn-lg" style={{ marginTop: 32 }} onClick={() => void handleSetup()} disabled={loading}>
            {loading ? 'Generating...' : 'Generate Secret Key'}
          </button>
        </div>
      )}

      {step === 2 && (
        <div className="card" style={{ padding: 32 }}>
          <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>Scan with your authenticator app</div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 8 }}>
            Use Google Authenticator, Authy, or any TOTP-compatible app.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginTop: 24 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div
                style={{
                  width: 180,
                  height: 180,
                  background: 'white',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 2,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden',
                }}
              >
                {qrData ? (
                  <img
                    src={`data:image/png;base64,${qrData}`}
                    alt="MFA QR code"
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                  />
                ) : (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', padding: 12, fontFamily: 'var(--font-mono)' }}>
                    QR data unavailable
                  </div>
                )}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Can&apos;t scan?</div>
              <div style={{ fontSize: 12, color: 'var(--text-primary)', marginTop: 8 }}>Enter this key manually:</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: 'var(--accent-blue)', letterSpacing: 3, marginTop: 8 }}>
                {secret}
              </div>
              <button className="link-muted" style={{ marginTop: 4, fontSize: 11 }} onClick={() => void navigator.clipboard.writeText(secret)}>
                Copy
              </button>
            </div>
          </div>

          <div style={{ height: 1, background: 'var(--border-subtle)', margin: '24px 0 20px' }} />

          <div style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)', marginBottom: 8 }}>
            Verification Code
          </div>
          <TOTPInputs value={totpCode} onChange={setTotpCode} />
          {error && <div style={{ marginTop: 12, fontSize: 13, color: 'var(--accent-red)' }}>{error}</div>}
          <button className="btn btn-primary btn-full btn-lg" style={{ marginTop: 24 }} onClick={() => void handleVerify()} disabled={loading}>
            {loading ? 'Verifying...' : 'Enable Two-Factor Authentication'}
          </button>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginTop: 16 }}>
            <span style={{ color: 'var(--accent-amber)', fontSize: 14 }}>⚠</span>
            <p style={{ fontSize: 12, color: 'var(--accent-amber)', lineHeight: 1.5 }}>
              Recovery codes are generated immediately after MFA is enabled. Save them offline.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
