import { useMemo, useState } from 'react';
import { Search, Upload } from 'lucide-react';

import { classifyApi, encryptApi, shareApi } from '../api';
import MFAChallengeModal from '../components/MFAChallengeModal';
import type { ClassificationResult, EncryptResult, ShareCreateResponse, SensitivityLevel } from '../types';
import { getApiErrorMessage } from '../utils/apiError';

const LEVEL_COLOR: Record<SensitivityLevel, string> = {
  public: 'var(--accent-green)',
  internal: 'var(--accent-blue)',
  confidential: 'var(--accent-amber)',
  highly_sensitive: 'var(--accent-red)',
};

const LEVEL_ORDER: SensitivityLevel[] = ['public', 'internal', 'confidential', 'highly_sensitive'];

export default function ClassifyPage() {
  const [mode, setMode] = useState<'text' | 'file'>('text');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClassificationResult | null>(null);
  const [encryptResult, setEncryptResult] = useState<EncryptResult | null>(null);
  const [shareResult, setShareResult] = useState<ShareCreateResponse | null>(null);
  const [sharePassword, setSharePassword] = useState('');
  const [shareExpiry, setShareExpiry] = useState('24h');
  const [shareMaxAccess, setShareMaxAccess] = useState(5);
  const [policyOverride, setPolicyOverride] = useState<SensitivityLevel | ''>('');
  const [encryptLoading, setEncryptLoading] = useState(false);
  const [shareLoading, setShareLoading] = useState(false);
  const [mfaOpen, setMfaOpen] = useState(false);
  const [mfaLoading, setMfaLoading] = useState(false);
  const [mfaError, setMfaError] = useState('');
  const [error, setError] = useState('');

  const plaintext = mode === 'text' ? text : result?.extracted_text || '';
  const recommendedLevel = result?.level;
  const overrideWarning = policyOverride && recommendedLevel
    && LEVEL_ORDER.indexOf(policyOverride) < LEVEL_ORDER.indexOf(recommendedLevel);

  const handleAnalyze = async () => {
    if (mode === 'text' && !text.trim()) {
      setError('Enter text to classify.');
      return;
    }
    if (mode === 'file' && !file) {
      setError('Choose a file to classify.');
      return;
    }

    setError('');
    setLoading(true);
    setEncryptResult(null);
    setShareResult(null);
    try {
      const res = mode === 'text' ? await classifyApi.classifyText(text) : await classifyApi.classifyFile(file as File);
      setResult(res.data);
      setPolicyOverride('');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Classification failed.'));
    } finally {
      setLoading(false);
    }
  };

  const encryptPayload = async (totpCode?: string) => {
    if (!result) return;
    if (mode === 'file' && file) {
      const payload = {
        classification_id: result.classification_id,
        file,
        policy_override_level: policyOverride || undefined,
      };
      if (totpCode) {
        return encryptApi.verifyMfaFile({ ...payload, totp_code: totpCode });
      }
      return encryptApi.encryptFile(payload);
    }
    if (!plaintext.trim()) return;
    const payload = {
      classification_id: result.classification_id,
      plaintext,
      policy_override_level: policyOverride || undefined,
    };
    if (totpCode) {
      return encryptApi.verifyMfa({ ...payload, totp_code: totpCode });
    }
    return encryptApi.encrypt(payload);
  };

  const handleEncrypt = async () => {
    setEncryptLoading(true);
    setError('');
    try {
      const res = await encryptPayload();
      setEncryptResult(res?.data || null);
      setShareResult(null);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (err?.response?.status === 403 && (detail === 'mfa_challenge_required' || detail?.code === 'mfa_challenge_required')) {
        setMfaError('');
        setMfaOpen(true);
      } else {
        setError(getApiErrorMessage(err, 'Encryption failed.'));
      }
    } finally {
      setEncryptLoading(false);
    }
  };

  const handleVerifyMfa = async (code: string) => {
    if (code.length !== 6) {
      setMfaError('Enter the 6-digit TOTP code.');
      return;
    }
    setMfaLoading(true);
    setMfaError('');
    try {
      const res = await encryptPayload(code);
      setEncryptResult(res?.data || null);
      setShareResult(null);
      setMfaOpen(false);
    } catch (err) {
      setMfaError(getApiErrorMessage(err, 'MFA verification failed.'));
    } finally {
      setMfaLoading(false);
    }
  };

  const handleShare = async () => {
    if (!encryptResult) return;
    setShareLoading(true);
    setError('');
    try {
      const res = await shareApi.create({
        payload_id: encryptResult.payload_id,
        password: sharePassword || undefined,
        expires_in: shareExpiry,
        max_access: shareMaxAccess,
      });
      setShareResult(res.data);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not create the share link.'));
    } finally {
      setShareLoading(false);
    }
  };

  const shareLink = shareResult ? `${window.location.origin}${shareResult.share_url}` : '';
  const policy = useMemo(() => result?.recommended_policy || null, [result]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div className="segmented-control">
            <button className={mode === 'text' ? 'active' : ''} onClick={() => setMode('text')}>Text Input</button>
            <button className={mode === 'file' ? 'active' : ''} onClick={() => setMode('file')}>File Upload</button>
          </div>
        </div>

        {mode === 'text' ? (
          <div style={{ position: 'relative' }}>
            <textarea
              className="form-textarea"
              style={{ height: 240, width: '100%' }}
              placeholder="Paste or type content to analyze..."
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
            <div style={{ position: 'absolute', bottom: 10, right: 14, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
              {text.length.toLocaleString()} / 50,000
            </div>
          </div>
        ) : (
          <div
            className={`drop-zone ${dragOver ? 'dragging' : ''}`}
            onDragOver={(event) => { event.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragOver(false);
              setFile(event.dataTransfer.files[0] || null);
            }}
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <Upload size={24} color="var(--text-muted)" />
            {file ? (
              <div style={{ fontSize: 14, color: 'var(--text-primary)' }}>{file.name}</div>
            ) : (
              <>
                <div style={{ fontSize: 14, color: 'var(--text-muted)' }}>Drop a file here or click to browse</div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>Supports .txt, .pdf, .docx, .md, .csv</div>
              </>
            )}
            <input id="file-input" type="file" accept=".txt,.pdf,.docx,.md,.csv" hidden onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16, gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          {error && <span style={{ fontSize: 13, color: 'var(--accent-red)' }}>{error}</span>}
          <button className="btn btn-primary" style={{ width: 140, height: 42 }} onClick={() => void handleAnalyze()} disabled={loading || (mode === 'text' ? !text.trim() : !file)}>
            <Search size={14} />
            {loading ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
      </div>

      {result && (
        <>
          <div className="section-divider"><span className="section-divider-label">ANALYSIS RESULTS</span></div>
          <div style={{ display: 'grid', gridTemplateColumns: '55% 45%', gap: 24 }}>
            <div className="card" style={{ padding: 24 }}>
              <div className="row-between" style={{ marginBottom: 12 }}>
                <span style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)' }}>Sensitivity</span>
                <span className="badge" style={{ fontSize: 16, color: LEVEL_COLOR[result.level], borderColor: LEVEL_COLOR[result.level], letterSpacing: 1, padding: '4px 10px' }}>
                  {result.level.toUpperCase()}
                </span>
              </div>
              <div className="row-between" style={{ marginBottom: 16 }}>
                <span style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)' }}>Confidence</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-primary)' }}>
                  {(result.confidence * 100).toFixed(1)}%
                </span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>{result.explanation_summary}</div>

              <div style={{ marginTop: 18 }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>Segment Analysis</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 14 }}>
                  {(result.segments || []).slice(0, 8).map((segment) => (
                    <div key={segment.segment_id} style={{ padding: 14, border: '1px solid var(--border-subtle)', background: 'var(--bg-primary)' }}>
                      <div className="row-between">
                        <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>
                          {segment.source === 'page' ? `Page ${segment.page}` : `Lines ${segment.line_start}-${segment.line_end}`}
                        </span>
                        <span className="badge" style={{ color: LEVEL_COLOR[segment.level], borderColor: LEVEL_COLOR[segment.level] }}>
                          {segment.level.replace('_', ' ')}
                        </span>
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 8 }}>{segment.content_preview}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>{segment.explanation}</div>
                      {segment.reasons.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
                          {segment.reasons.map((reason) => (
                            <span key={`${segment.segment_id}-${reason.pattern}-${reason.line}-${reason.col_start}`} className="badge" style={{ color: 'var(--accent-amber)', borderColor: 'var(--accent-amber)' }}>
                              {reason.label} @ line {reason.line}:{reason.col_start}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {policy && (
              <div className="card" style={{ padding: 24 }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>Recommended Policy</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>{policy.display_name}</div>
                <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {[
                    ['ENCRYPTION', policy.encryption_algo],
                    ['KEY DERIVATION', policy.key_derivation || '—'],
                    ['KDF ITERATIONS', policy.kdf_iterations?.toLocaleString() || '—'],
                    ['SIGNING', policy.signing_algo || (policy.signing_required ? 'Required' : '—')],
                    ['REQUIRE MFA', policy.require_mfa ? 'Yes' : 'No'],
                  ].map(([key, value]) => (
                    <div key={key} className="row-between">
                      <span style={{ fontSize: 12, textTransform: 'uppercase', color: 'var(--text-muted)' }}>{key}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-primary)' }}>{value}</span>
                    </div>
                  ))}
                </div>

                <div style={{ marginTop: 20 }}>
                  <label className="form-label">Override Encryption Policy</label>
                  <select className="form-select" value={policyOverride} onChange={(event) => setPolicyOverride(event.target.value as SensitivityLevel | '')}>
                    <option value="">Use recommended policy</option>
                    {LEVEL_ORDER.map((level) => (
                      <option key={level} value={level}>{level.replace('_', ' ')}</option>
                    ))}
                  </select>
                  {overrideWarning && (
                    <div style={{ marginTop: 8, fontSize: 12, color: 'var(--accent-amber)' }}>
                      Warning: this override is weaker than the recommended policy.
                    </div>
                  )}
                </div>

                <div style={{ height: 1, background: 'var(--border-subtle)', margin: '20px 0 16px' }} />
                <button className="btn btn-primary btn-full" style={{ height: 42 }} onClick={() => void handleEncrypt()} disabled={encryptLoading || (mode === 'file' ? !file : !plaintext.trim())}>
                  {encryptLoading ? 'Encrypting...' : 'Encrypt Now'}
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {encryptResult && (
        <div className="card" style={{ padding: 24 }}>
          <div className="row-between">
            <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--accent-green)' }}>Encryption Complete</div>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' }}>{encryptResult.encryption_time_ms}ms</span>
          </div>

          <div className="grid-3" style={{ marginTop: 18 }}>
            {[
              ['PAYLOAD ID', encryptResult.payload_id],
              ['ALGORITHM', encryptResult.encryption_algo],
              ['SIZE', `${encryptResult.original_size}B → ${encryptResult.encrypted_size}B`],
            ].map(([label, value]) => (
              <div key={label}>
                <div style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-muted)' }}>{label}</div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)', marginTop: 6 }}>{value}</div>
              </div>
            ))}
          </div>

          <div style={{ height: 1, background: 'var(--border-subtle)', margin: '20px 0 16px' }} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
            <div className="form-group">
              <label className="form-label">Share Expiry</label>
              <select className="form-select" value={shareExpiry} onChange={(event) => setShareExpiry(event.target.value)}>
                {['1h', '6h', '12h', '24h', '7d', '30d', 'never'].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Max Access</label>
              <input className="form-input" type="number" min={1} value={shareMaxAccess} onChange={(event) => setShareMaxAccess(Number(event.target.value) || 1)} />
            </div>
            <div className="form-group">
              <label className="form-label">Share Password</label>
              <input className="form-input" type="password" value={sharePassword} onChange={(event) => setSharePassword(event.target.value)} placeholder="Optional" />
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-outline btn-sm" onClick={() => void handleShare()} disabled={shareLoading}>
              {shareLoading ? 'Generating...' : 'Generate Link'}
            </button>
          </div>
          {shareResult && (
            <div style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', gap: 10 }}>
                <input className="form-input" readOnly value={shareLink} />
                <button
                  className="btn btn-outline btn-sm"
                  type="button"
                  onClick={() => void navigator.clipboard.writeText(shareLink)}
                >
                  Copy Link
                </button>
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
                Token prefix: <span style={{ fontFamily: 'var(--font-mono)' }}>{shareResult.token_prefix}</span>
              </div>
            </div>
          )}
        </div>
      )}

      <MFAChallengeModal
        open={mfaOpen}
        loading={mfaLoading}
        onClose={() => setMfaOpen(false)}
        onSubmit={handleVerifyMfa}
        error={mfaError}
      />
    </div>
  );
}
