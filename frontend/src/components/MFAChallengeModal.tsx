import { useEffect, useRef, useState } from 'react';

type Props = {
  open: boolean;
  loading?: boolean;
  onClose: () => void;
  onSubmit: (code: string) => Promise<void> | void;
  error?: string;
  title?: string;
  message?: string;
};

export default function MFAChallengeModal({
  open,
  loading,
  onClose,
  onSubmit,
  error,
  title = 'MFA Verification Required',
  message = 'This encryption policy requires a fresh TOTP code before execution.',
}: Props) {
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const refs = useRef<HTMLInputElement[]>([]);

  useEffect(() => {
    if (!open) {
      setCode(['', '', '', '', '', '']);
    }
  }, [open]);

  if (!open) return null;

  const joined = code.join('');

  const handleInput = (index: number, value: string) => {
    if (!/^\d?$/.test(value)) return;
    const next = [...code];
    next[index] = value;
    setCode(next);
    if (value && index < 5) refs.current[index + 1]?.focus();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(event) => event.stopPropagation()}>
        <h3 style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>{title}</h3>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 8 }}>
          {message}
        </p>
        <div className="totp-inputs" style={{ marginTop: 20 }}>
          {code.map((digit, index) => (
            <input
              key={index}
              ref={(element) => { if (element) refs.current[index] = element; }}
              className="totp-input"
              maxLength={1}
              value={digit}
              onChange={(event) => handleInput(index, event.target.value)}
              type="text"
              inputMode="numeric"
            />
          ))}
        </div>
        {error && <div style={{ marginTop: 12, fontSize: 12, color: 'var(--accent-red)' }}>{error}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary btn-sm" onClick={() => void onSubmit(joined)} disabled={loading || joined.length !== 6}>
            {loading ? 'Verifying...' : 'Verify & Encrypt'}
          </button>
        </div>
      </div>
    </div>
  );
}
