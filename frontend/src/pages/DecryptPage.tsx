import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { decryptApi } from '../api';
import type { DecryptResult } from '../types';
import { getApiErrorMessage } from '../utils/apiError';

export default function DecryptPage() {
  const { token } = useParams<{ token: string }>();
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<DecryptResult | null>(null);

  const handleDecrypt = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await decryptApi.decryptShare(token!, password || undefined);
      setResult(res.data);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Decryption failed. Check the password and try again.'));
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!result?.file_data_base64) return;
    const binary = atob(result.file_data_base64);
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    const blob = new Blob([bytes], { type: result.content_type || 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = result.file_name || 'download';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{
      minHeight: '100vh', background: 'var(--bg-primary)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24,
    }}>
      <div style={{ width: '100%', maxWidth: 480 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 500, letterSpacing: 3, color: 'var(--text-muted)' }}>WEAVER</div>
          <div style={{ width: 60, height: 1, background: 'var(--border-subtle)', margin: '6px auto 24px' }} />
          <div style={{ fontSize: 20, fontWeight: 500, color: 'var(--text-primary)' }}>Secure Content Access</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 8 }}>This content was encrypted and shared with you.</div>
        </div>

        <form onSubmit={handleDecrypt} style={{ marginTop: 32 }}>
          <div className="card" style={{ padding: 24 }}>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Enter the share password if one was set. After decryption, Weaver will show the content or let you download the original file.
            </div>
            <div style={{ marginTop: 16 }}>
              <div className="form-group">
                <label className="form-label">PASSWORD (if required)</label>
                <input className="form-input" type="password" placeholder="Enter share password" value={password} onChange={e => setPassword(e.target.value)} />
              </div>
            </div>
            {error && <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(181,74,74,0.1)', border: '1px solid var(--accent-red)', borderRadius: 2, fontSize: 13, color: 'var(--accent-red)' }}>{error}</div>}
            <button type="submit" className="btn btn-primary btn-full btn-lg" style={{ marginTop: 16 }} disabled={loading}>
              {loading ? 'Decrypting...' : 'Decrypt Content'}
            </button>
          </div>
        </form>

        {result && (
          <div className="card" style={{ marginTop: 16, padding: 24 }}>
            <div className="row-between" style={{ gap: 12, alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)' }}>
                  {result.content_kind === 'file' ? 'Shared File' : 'Shared Content'}
                </div>
                <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)', marginTop: 6 }}>
                  {result.file_name || 'Decrypted Content'}
                </div>
              </div>
              {result.content_kind === 'file' && result.file_data_base64 && (
                <button className="btn btn-primary btn-sm" type="button" onClick={handleDownload}>
                  Download Original
                </button>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {result.integrity_verified && (
                <span style={{ fontSize: 12, color: 'var(--accent-green)', border: '1px solid var(--accent-green)', padding: '2px 8px', borderRadius: 2 }}>✓ Integrity Verified</span>
              )}
              {result.signature_verified === true && (
                <span style={{ fontSize: 12, color: 'var(--accent-green)', border: '1px solid var(--accent-green)', padding: '2px 8px', borderRadius: 2 }}>✓ Signature Valid</span>
              )}
              {result.signature_verified === false && (
                <span style={{ fontSize: 12, color: 'var(--accent-red)', border: '1px solid var(--accent-red)', padding: '2px 8px', borderRadius: 2 }}>✗ Signature Invalid</span>
              )}
              {result.signature_verified == null && (
                <span style={{ fontSize: 12, color: 'var(--text-muted)', border: '1px solid var(--border-subtle)', padding: '2px 8px', borderRadius: 2 }}>No Signature</span>
              )}
              <span style={{ fontSize: 12, color: 'var(--accent-blue)', border: '1px solid var(--accent-blue)', padding: '2px 8px', borderRadius: 2 }}>{result.encryption_algo}</span>
            </div>
            <div style={{ height: 1, background: 'var(--border-subtle)', margin: '16px 0' }} />
            {result.content_kind === 'file' ? (
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                The original file is ready. Use <span style={{ fontFamily: 'var(--font-mono)' }}>Download Original</span> to save <span style={{ fontFamily: 'var(--font-mono)' }}>{result.file_name || 'the file'}</span>.
              </div>
            ) : (
              <pre style={{
                fontFamily: 'var(--font-mono)', fontSize: 14, color: 'var(--text-primary)',
                lineHeight: 1.6, padding: 16, background: 'var(--bg-base)', borderRadius: 2,
                maxHeight: 400, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all'
              }}>
                {result.plaintext}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
