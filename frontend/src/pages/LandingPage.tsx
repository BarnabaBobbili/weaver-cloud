import './landing.css';
import { useEffect, useRef, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';

/* ──────────────────────────────────────────
   TYPES for the guest predict API
────────────────────────────────────────── */
interface Classification {
  level: string;
  confidence: number;
  explanation: string;
  recommended_algorithm: string;
  reasoning: string;
  segments?: Array<{ text: string; level: string; start: number; end: number }>;
}

interface EncryptResult { ciphertext: string; algorithm_used: string; key_hint?: string; }
interface GuestShareResp { share_url: string; expires_in_hours: number; }

/* ──────────────────────────────────────────
   HOOK – scroll reveal
────────────────────────────────────────── */
function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('.lp-reveal');
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('in-view'); });
    }, { threshold: 0.08 });
    els.forEach(el => io.observe(el));
    return () => io.disconnect();
  }, []);
}

function useFillText() {
  useEffect(() => {
    const els = document.querySelectorAll('.lp-fill-text, .lp-services-subtext, .lp-portfolio-fill');
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('filled'); });
    }, { threshold: 0.3 });
    els.forEach(el => io.observe(el));
    return () => io.disconnect();
  }, []);
}

/* ──────────────────────────────────────────
   LEVEL COLORS
────────────────────────────────────────── */
const LEVEL_COLORS: Record<string, string> = {
  PUBLIC:       '#4caf79',
  INTERNAL:     '#3a8fcf',
  CONFIDENTIAL: '#e6a817',
  RESTRICTED:   '#e05555',
};

function levelColor(l: string) { return LEVEL_COLORS[l?.toUpperCase()] ?? '#888'; }

/* ──────────────────────────────────────────
   TRY-IT PANEL (inside dark dev section)
────────────────────────────────────────── */
function TryItPanel() {
  const [tab, setTab] = useState<'text' | 'file'>('text');
  const [action, setAction] = useState<'classify' | 'encrypt' | 'share'>('classify');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [classification, setClassification] = useState<Classification | null>(null);
  const [encrypted, setEncrypted] = useState<EncryptResult | null>(null);
  const [shared, setShared] = useState<GuestShareResp | null>(null);
  const [shareExp, setShareExp] = useState(6);
  const [algo, setAlgo] = useState('auto');
  const [shareLimit, setShareLimit] = useState('3');
  const fileRef = useRef<HTMLInputElement>(null);

  const BASE = 'http://localhost:8000/api/v1';

  const handleClassify = useCallback(async () => {
    if (!text.trim() && !file) return;
    setLoading(true); setError(''); setClassification(null); setEncrypted(null); setShared(null);
    try {
      let res: Classification;
      if (file) {
        const fd = new FormData(); fd.append('file', file);
        const r = await fetch(`${BASE}/guest/classify-file`, { method: 'POST', body: fd });
        if (!r.ok) throw new Error((await r.json()).detail ?? 'Error'); res = await r.json();
      } else {
        const r = await fetch(`${BASE}/guest/classify`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        if (!r.ok) throw new Error((await r.json()).detail ?? 'Error'); res = await r.json();
      }
      setClassification(res);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [text, file]);

  const handleEncrypt = useCallback(async () => {
    if (!text.trim() && !file) return;
    setLoading(true); setError(''); setEncrypted(null);
    try {
      let r: Response;
      if (file) {
        const fd = new FormData(); fd.append('file', file);
        if (algo !== 'auto') fd.append('algorithm', algo);
        r = await fetch(`${BASE}/guest/encrypt-file`, { method: 'POST', body: fd });
      } else {
        r = await fetch(`${BASE}/guest/encrypt`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, algorithm: algo === 'auto' ? undefined : algo })
        });
      }
      if (!r.ok) throw new Error((await r.json()).detail ?? 'Encryption failed');
      setEncrypted(await r.json());
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [text, file, algo]);

  const handleShare = useCallback(async () => {
    const payload = file ? null : text;
    if (!payload && !file) return;
    setLoading(true); setError(''); setShared(null);
    try {
      let r: Response;
      if (file) {
        const fd = new FormData(); fd.append('file', file);
        fd.append('expires_in_hours', String(shareExp));
        fd.append('max_downloads', shareLimit);
        r = await fetch(`${BASE}/guest/share-file`, { method: 'POST', body: fd });
      } else {
        r = await fetch(`${BASE}/guest/share`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, expires_in_hours: shareExp, max_downloads: parseInt(shareLimit) })
        });
      }
      if (!r.ok) throw new Error((await r.json()).detail ?? 'Share failed');
      setShared(await r.json());
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, [text, file, shareExp, shareLimit]);

  const run = () => {
    if (action === 'classify') handleClassify();
    else if (action === 'encrypt') handleEncrypt();
    else handleShare();
  };

  return (
    <div className="lp-try-grid">
      {/* Left – input */}
      <div className="lp-try-panel">
        <div className="lp-try-tabs">
          <button className={`lp-try-tab ${tab === 'text' ? 'active' : ''}`} onClick={() => setTab('text')}>Text</button>
          <button className={`lp-try-tab ${tab === 'file' ? 'active' : ''}`} onClick={() => setTab('file')}>File</button>
        </div>
        <div className="lp-try-body">
          {tab === 'text' ? (
            <textarea
              className="lp-try-textarea"
              placeholder="Paste any text — PII, contracts, reports…"
              value={text}
              onChange={e => setText(e.target.value)}
            />
          ) : (
            <>
              <div
                className="lp-try-drop"
                onClick={() => fileRef.current?.click()}
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) setFile(f); }}
              >
                {file ? (
                  <span className="lp-try-drop-label">📄 {file.name}</span>
                ) : (
                  <>
                    <span className="lp-try-drop-label">Drop file here or click</span>
                    <span className="lp-try-drop-hint">PDF, DOCX, TXT, MD (max 10 MB)</span>
                  </>
                )}
              </div>
              <input ref={fileRef} type="file" accept=".pdf,.docx,.txt,.md" style={{ display: 'none' }}
                onChange={e => setFile(e.target.files?.[0] ?? null)} />
            </>
          )}

          {/* Action selector */}
          <div className="lp-try-row">
            {(['classify', 'encrypt', 'share'] as const).map(a => (
              <button
                key={a}
                className={`lp-try-btn ${action === a ? 'lp-try-btn-primary' : 'lp-try-btn-secondary'}`}
                onClick={() => setAction(a)}
              >
                {a === 'classify' ? '🔍 Classify' : a === 'encrypt' ? '🔐 Encrypt' : '🔗 Share'}
              </button>
            ))}
          </div>

          {/* Settings */}
          {action === 'encrypt' && (
            <div className="lp-try-settings">
              <div className="lp-try-field">
                <span className="lp-try-label">Algorithm</span>
                <select className="lp-try-select" value={algo} onChange={e => setAlgo(e.target.value)}>
                  <option value="auto">AI Recommended</option>
                  <option value="AES-256-GCM">AES-256-GCM</option>
                  <option value="ChaCha20-Poly1305">ChaCha20</option>
                  <option value="RSA-OAEP-2048">RSA-OAEP</option>
                </select>
              </div>
            </div>
          )}
          {action === 'share' && (
            <div className="lp-try-settings">
              <div className="lp-try-field">
                <span className="lp-try-label">Expires (h)</span>
                <input className="lp-try-input" type="number" min={1} max={24} value={shareExp} onChange={e => setShareExp(Number(e.target.value))} />
              </div>
              <div className="lp-try-field">
                <span className="lp-try-label">Max DLs</span>
                <select className="lp-try-select" value={shareLimit} onChange={e => setShareLimit(e.target.value)}>
                  {['1','3','5','10','unlimited'].map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
            </div>
          )}

          <div className="lp-try-row" style={{ marginTop: 20 }}>
            <button className="lp-try-btn lp-try-btn-primary" onClick={run} disabled={loading || (!text && !file)}>
              {loading ? 'Processing…' : action === 'classify' ? 'Classify' : action === 'encrypt' ? 'Encrypt' : 'Create Share Link'}
            </button>
            {(text || file) && (
              <button className="lp-try-btn lp-try-btn-tertiary" onClick={() => { setText(''); setFile(null); setClassification(null); setEncrypted(null); setShared(null); setError(''); }}>Clear</button>
            )}
          </div>
          {error && <div className="lp-try-error">⚠ {error}</div>}
        </div>
      </div>

      {/* Right – result */}
      <div className="lp-try-result">
        <div className="lp-try-result-label">Result</div>

        {!classification && !encrypted && !shared && !loading && (
          <div className="lp-result-empty">
            <div style={{ fontSize: 32 }}>🔍</div>
            <div>Run a classification, encryption or share to see results here</div>
          </div>
        )}

        {loading && (
          <div className="lp-result-empty">
            <div style={{ fontSize: 24 }}>⏳</div>
            <div>Analysing…</div>
          </div>
        )}

        {classification && (
          <>
            <div className="lp-level-badge" style={{ color: levelColor(classification.level) }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: levelColor(classification.level), display: 'inline-block' }} />
              {classification.level}
            </div>
            <div className="lp-conf-bar">
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,.35)', minWidth: 72 }}>Confidence</span>
              <div className="lp-conf-track">
                <div className="lp-conf-fill" style={{ width: `${Math.round(classification.confidence * 100)}%`, background: levelColor(classification.level) }} />
              </div>
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,.5)', minWidth: 32, textAlign: 'right' }}>{Math.round(classification.confidence * 100)}%</span>
            </div>
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,.65)', lineHeight: 1.6, marginBottom: 12 }}>{classification.explanation}</div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,.3)', marginBottom: 8 }}>
              Recommended: <span style={{ color: '#2ca8fe', fontFamily: 'monospace' }}>{classification.recommended_algorithm}</span>
            </div>
            {classification.segments && classification.segments.length > 0 && (
              <>
                <div style={{ fontSize: 10, letterSpacing: 1.5, textTransform: 'uppercase', color: 'rgba(255,255,255,.25)', marginBottom: 8 }}>Segments</div>
                {classification.segments.slice(0, 3).map((s, i) => (
                  <div className="lp-segment-card" key={i}>
                    <div className="lp-segment-row">
                      <span className="lp-segment-loc">chars {s.start}–{s.end}</span>
                      <span className="lp-segment-lvl" style={{ color: levelColor(s.level) }}>{s.level}</span>
                    </div>
                    <div className="lp-segment-text">"{s.text.slice(0, 80)}{s.text.length > 80 ? '…' : ''}"</div>
                  </div>
                ))}
              </>
            )}
            <div className="lp-result-limits">
              Guest mode · 5 req/hr · <Link to="/register" style={{ color: '#2ca8fe' }}>Sign up for unlimited access</Link>
            </div>
          </>
        )}

        {encrypted && (
          <>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,.35)', marginBottom: 8 }}>
              Algorithm: <span style={{ color: '#2ca8fe', fontFamily: 'monospace' }}>{encrypted.algorithm_used}</span>
            </div>
            <textarea
              readOnly
              className="lp-try-textarea"
              style={{ height: 200, fontSize: 11, fontFamily: 'monospace', color: '#4caf79' }}
              value={encrypted.ciphertext}
            />
            {encrypted.key_hint && (
              <div style={{ marginTop: 8, fontSize: 11, color: 'rgba(255,255,255,.3)' }}>Key hint: {encrypted.key_hint}</div>
            )}
            <div className="lp-result-limits">Sign in to save encrypted files and manage keys.</div>
          </>
        )}

        {shared && (
          <>
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,.6)', marginBottom: 10 }}>Share link created · expires in {shared.expires_in_hours}h</div>
            <input readOnly className="lp-share-url" value={`${window.location.origin}${shared.share_url}`} onClick={e => (e.target as HTMLInputElement).select()} />
            <button className="lp-try-btn lp-try-btn-secondary" style={{ marginTop: 12 }}
              onClick={() => navigator.clipboard.writeText(`${window.location.origin}${shared.share_url}`)}>
              Copy Link
            </button>
            <div className="lp-result-limits">Guest links expire after 24 h. <Link to="/register" style={{ color: '#2ca8fe' }}>Sign up</Link> for unlimited duration.</div>
          </>
        )}
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────
   ACCESS MATRIX DATA
────────────────────────────────────────── */
const ACCESS_MATRIX = [
  ['Classify Text (Guest)',      '✓', '✓', '✓', '✓'],
  ['Classify File (Guest)',      '✓', '✓', '✓', '✓'],
  ['Encrypt Text (Guest)',       '✓', '✓', '✓', '✓'],
  ['Guest Share Link (24 h max)','✓', '✓', '✓', '✓'],
  ['Unlimited Share Duration',   '—', '✓', '✓', '✓'],
  ['Share Link Expiry Control',  '—', '✓', '✓', '✓'],
  ['View Own Encryption History','—', '✓', '✓', '✓'],
  ['Download History & Reports', '—', '—', '✓', '✓'],
  ['MFA Enforcement',            '—', 'opt','opt','✓'],
  ['XAI Explanations',           '—', '—', '✓', '✓'],
  ['Dashboard & Stats',          '—', '✓', '✓', '✓'],
  ['User Management',            '—', '—', '—', '✓'],
  ['System Audit Logs',          '—', '—', '—', '✓'],
  ['Crypto Policy Override',     '—', '—', '—', '✓'],
  ['Rate Limits',                '5/hr','100/hr','500/hr','∞'],
];

/* ──────────────────────────────────────────
   ABOUT STAT CARDS
────────────────────────────────────────── */
const STATS = [
  { num: '4',    label: 'Sensitivity levels — Public to Restricted', video: '/media/about/ball-color.mp4' },
  { num: '6+',   label: 'Encryption algorithms, AI-selected',        video: '/media/about/pruzina-color.mp4' },
  { num: '↗97%', label: 'Classification accuracy on real docs',      video: '/media/about/time-color.mp4' },
  { num: '0ms',  label: 'Manual policy decisions needed',            video: '/media/about/volchek-color.mp4' },
];

/* ──────────────────────────────────────────
   PORTFOLIO CARDS
────────────────────────────────────────── */
const PORTFOLIO_CARDS = [
  { title: 'Medical Records', sub: 'RESTRICTED · AES-256-GCM', color: '#1a2a4a' },
  { title: 'Internal Memo',   sub: 'INTERNAL · ChaCha20',      color: '#1a3a2a' },
  { title: 'Public Docs',     sub: 'PUBLIC · No encryption',   color: '#2a2a1a' },
  { title: 'HR Contract',     sub: 'CONFIDENTIAL · RSA-OAEP',  color: '#3a1a2a' },
];

/* ──────────────────────────────────────────
   TYPING ANIMATION HOOK
────────────────────────────────────────── */
const WORDS = ['Encryption.', 'Privacy.', 'Protection.', 'Compliance.'];
function useTyping() {
  const [word, setWord] = useState(WORDS[0]);
  const [, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => {
      setIdx(i => { const n = (i + 1) % WORDS.length; setWord(WORDS[n]); return n; });
    }, 2800);
    return () => clearInterval(t);
  }, []);
  return word;
}

/* ──────────────────────────────────────────
   MAIN COMPONENT
────────────────────────────────────────── */
export default function LandingPage() {
  const typingWord = useTyping();
  const [, setMenuOpen] = useState(false);
  useReveal();
  useFillText();

  const scrollTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });

  return (
    <div className="lp-root">

      {/* ── STICKY TOP-RIGHT ── */}
      <div className="lp-sticky">
        <Link to="/login" className="lp-sticky-cta">
          <div className="lp-sticky-cta-inner">
            <span>Sign In</span>
            <span>Sign In</span>
          </div>
        </Link>
        <button className="lp-menu-btn" onClick={() => setMenuOpen(o => !o)} aria-label="Menu">
          <div className="lp-menu-btn-bars">
            <span /><span /><span />
          </div>
        </button>
      </div>

      {/* ── HERO ── */}
      <section className="lp-hero">
        <div className="lp-hero-bg">
          <video
            className="lp-hero-video"
            src="/media/hero.mp4"
            autoPlay muted loop playsInline
            poster="/media/hero_poster.jpg"
          />
          <div className="lp-hero-overlay" />
          <div className="lp-hero-inner">

            {/* Header */}
            <header className="lp-hero-header">
              <div className="lp-hero-logo">
                <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                  <rect width="28" height="28" rx="6" fill="#2ca8fe"/>
                  <path d="M7 21L14 7L21 21" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M10 16h8" stroke="#fff" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                <span className="lp-hero-logo-text">WEAVER</span>
              </div>
              <nav className="lp-hero-nav">
                {['Features', 'Try It', 'Access', 'Sign In', 'Sign Up'].map(n => (
                  <Link
                    key={n}
                    to={n === 'Sign In' ? '/login' : n === 'Sign Up' ? '/register' : `#${n.toLowerCase().replace(' ','-')}`}
                    className="lp-hero-nav-item"
                  >
                    <span><span>{n}</span><span>{n}</span></span>
                  </Link>
                ))}
              </nav>
            </header>

            {/* Title */}
            <div className="lp-hero-content">
              <div className="lp-hero-left">
                <div className="lp-hero-title">
                  <div className="lp-hero-title-we">We secure</div>
                  <div className="lp-hero-title-awesome">
                    <i>Adaptive</i>
                    <span className="lp-scroll-btn" style={{ fontSize: '0.25em' }} />
                  </div>
                  <div className="lp-hero-title-typing">
                    {typingWord}
                    <span style={{ display: 'inline-block', width: '.12em', height: '.75em', background: '#fff', marginLeft: '.08em', verticalAlign: 'middle', animation: 'aw-blink 1.2s linear infinite' }} />
                  </div>
                </div>
              </div>
              <div className="lp-hero-right">
                <nav className="lp-hero-right-nav">
                  <a>AI Crypto Policy Engine</a>
                  <Link to="/register">Get Started →</Link>
                  <Link to="/login">Sign In</Link>
                </nav>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FOCUSED / MARQUEE ── */}
      <div className="lp-focused">
        <div className="lp-focused-list">
          {[0,1].map(i => (
            <div key={i} className="lp-focused-item">
              <div className="lp-focused-text">
                Data‑driven&nbsp;&nbsp;•&nbsp;&nbsp;Security‑focused&nbsp;&nbsp;•&nbsp;&nbsp;Crypto‑protected&nbsp;&nbsp;•&nbsp;&nbsp;
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── SERVICES / FEATURES ── */}
      <section id="features" className="lp-services">
        <div className="lp-container">
          <span className="lp-section-label">Platform</span>
          <div
            className="lp-services-subtext"
            data-text="Weaver automatically classifies, encrypts and shares your sensitive data — with zero manual decisions."
          >
            Weaver automatically classifies, encrypts and shares your sensitive data — with zero manual decisions.
          </div>
          <div className="lp-services-list">
            {[
              { title: 'Classify', desc: 'ML model reads your text or file and assigns a sensitivity level — Public, Internal, Confidential or Restricted.', tags: ['Text', 'Files', 'PDF', 'DOCX', 'MD'], color: '#1a2233' },
              { title: 'Encrypt', desc: 'The recommended cipher is applied automatically. Advanced users can override. Keys are managed server‑side.', tags: ['AES-256-GCM', 'ChaCha20', 'RSA-OAEP'], color: '#0f1f18' },
              { title: 'Share', desc: 'Create encrypted, time-limited share links. Choose expiry and download limits. Guests get 24 h maximum.', tags: ['Time-limited', 'DL caps', 'Revoke'], color: '#1f1a0f' },
            ].map(s => (
              <div key={s.title} className="lp-services-item">
                <div className="lp-service-card">
                  <div className="lp-service-card-bg" style={{ background: s.color }} />
                  <div className="lp-service-card-body">
                    <div className="lp-service-card-title">{s.title}</div>
                    <div className="lp-service-card-desc">{s.desc}</div>
                    <div className="lp-service-tags">
                      {s.tags.map(t => <span key={t} className="lp-service-tag">{t}</span>)}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── ABOUT / STATS ── */}
      <section className="lp-about">
        <div className="lp-container">
          <span className="lp-section-label">About</span>
          <div className="lp-about-head">
            <div className="lp-about-head-title">Why Weaver</div>
          </div>
          <div className="lp-about-content">
            <div className="lp-about-left">
              <p
                className="lp-fill-text"
                data-text="Weaver is an AI-driven adaptive cryptographic policy engine. It reads your content, understands context and selects the right encryption — automatically."
              >
                Weaver is an AI-driven adaptive cryptographic policy engine. It reads your content, understands context and selects the right encryption — automatically.
              </p>
              <p
                className="lp-fill-text"
                data-text="No security PhD required. Paste text, upload a file — Weaver does the rest."
              >
                No security PhD required. Paste text, upload a file — Weaver does the rest.
              </p>
              <div className="lp-about-stat-title">By the numbers</div>
              <div className="lp-about-stats">
                {STATS.map(s => (
                  <div key={s.num} className="lp-about-stat-item lp-reveal">
                    <div className="lp-about-card">
                      <video
                        className="lp-about-card-video"
                        src={s.video}
                        autoPlay muted loop playsInline
                      />
                      <div className="lp-about-card-body">
                        <div className="lp-about-card-num">{s.num}</div>
                        <div className="lp-about-card-desc">{s.label}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── LOGO MARQUEE ── */}
      <div className="lp-logos" style={{ borderTop: '1px solid #e9e9e9', borderBottom: '1px solid #e9e9e9' }}>
        <div className="lp-logos-inner">
          {[0,1].map(i => (
            <div key={i} className="lp-logos-track">
              {['Healthcare','Finance','Legal','HR','Government','Education','Defence','Research'].map(l => (
                <div key={l} className="lp-logo-item">{l}</div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* ── DEVELOPMENT / DARK SECTION ── */}
      <section className="lp-dev" id="try-it">
        {/* Ghost marquee background */}
        <div className="lp-dev-marquee">
          <div className="lp-dev-marquee-inner">
            {[0,1].map(i => (
              <div key={i} className="lp-dev-marquee-track">
                <div className="lp-dev-marquee-text">SECURE — CLASSIFY — ENCRYPT — SHARE&nbsp;</div>
                <div className="lp-dev-marquee-text">SECURE — CLASSIFY — ENCRYPT — SHARE&nbsp;</div>
              </div>
            ))}
          </div>
        </div>

        {/* SVG Path Connector */}
        <div className="lp-dev-line">
          <svg className="" width="1157" height="64" viewBox="0 0 1157 64" fill="none">
            <path d="M1157 1H467.5C428.5 1 406 24 406 64" />
          </svg>
        </div>

        <div className="lp-container">
          <div className="lp-dev-content" style={{ paddingTop: 80 }}>
            <div className="lp-dev-title">
              <div className="lp-dev-title-main">
                <span>Try</span>
                <span style={{ fontStyle: 'italic' }}>it</span>
                <span>now</span>
              </div>
              <div className="lp-dev-title-stars">✦ no<br />login</div>
            </div>

            {/* TRY IT PANEL */}
            <div style={{ marginTop: 48 }}>
              <TryItPanel />
            </div>

            <div className="lp-dev-bottom">
              <div className="lp-dev-desc">
                Guest mode: 5 requests / hour. Sign up for unlimited access, history, and dashboard analytics.
              </div>
              <div className="lp-dev-btns">
                <Link to="/register" className="lp-dev-btn-white">Create Account</Link>
                <Link to="/login" className="lp-dev-btn-gray">Sign In</Link>
              </div>
            </div>
          </div>

          {/* Pipeline explainer inside dark section */}
          <div style={{ paddingTop: 80, paddingBottom: 80 }}>
            <span className="lp-section-label" style={{ color: 'rgba(255,255,255,.4)' }}>How it works</span>
            <div style={{ display: 'flex', gap: 0, marginTop: 40, position: 'relative' }}>
              <div style={{ position: 'absolute', top: 20, left: 0, right: 0, height: 1, background: 'rgba(255,255,255,.08)' }} />
              {[
                { n: '01', title: 'Input', desc: 'Paste text or upload PDF/DOCX/MD' },
                { n: '02', title: 'Classify', desc: 'ML model assigns sensitivity level with XAI reasoning' },
                { n: '03', title: 'Encrypt', desc: 'Optimal cipher selected and applied automatically' },
                { n: '04', title: 'Share', desc: 'Time-limited encrypted link created with access controls' },
              ].map(step => (
                <div key={step.n} style={{ flex: 1, padding: '0 20px' }}>
                  <div style={{ width: 40, height: 40, borderRadius: '50%', border: '1px solid rgba(255,255,255,.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', font: '400 12px/1 monospace', color: 'rgba(255,255,255,.5)', marginBottom: 20, background: '#0d0f11', position: 'relative', zIndex: 1 }}>{step.n}</div>
                  <div style={{ font: '500 18px/1.2 Plus Jakarta Sans, sans-serif', color: '#fff', marginBottom: 10 }}>{step.title}</div>
                  <div style={{ font: '400 14px/1.5 Inter', color: 'rgba(255,255,255,.45)' }}>{step.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── ACCESS MATRIX ── */}
      <section className="lp-access" id="access">
        <div className="lp-container">
          <div className="lp-access-head lp-reveal">
            <span className="lp-section-label">Access</span>
            <h2 className="lp-access-title">Who can do what</h2>
            <p className="lp-access-sub">Full feature parity for registered users. Guests can try without signing in.</p>
          </div>
          <div className="lp-matrix lp-reveal lp-reveal-d1">
            <table>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th className="c-guest">Guest</th>
                  <th className="c-viewer">User</th>
                  <th className="c-analyst">Analyst</th>
                  <th className="c-admin">Admin</th>
                </tr>
              </thead>
              <tbody>
                {ACCESS_MATRIX.map(([feat,...cols]) => (
                  <tr key={feat as string}>
                    <td>{feat}</td>
                    {cols.map((v,i) => (
                      <td key={i} className={['c-guest','c-viewer','c-analyst','c-admin'][i]}>
                        {v === '✓' ? '✓' : v === '—' ? <span className="c-dash">—</span> : v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── PORTFOLIO ── */}
      <section className="lp-portfolio">
        <div className="lp-container">
          <div className="lp-portfolio-head">
            <div>
              <span className="lp-portfolio-label lp-reveal">Examples</span>
              <div
                className="lp-portfolio-fill lp-reveal lp-reveal-d1"
                data-text="See how Weaver classifies and encrypts real document types."
              >
                See how Weaver classifies and encrypts real document types.
              </div>
            </div>
            <div>
              <h2 className="lp-portfolio-title lp-reveal lp-reveal-d2">Real Docs, Real Security</h2>
            </div>
          </div>

          <div className="lp-portfolio-list">
            <div className="lp-portfolio-row">
              {PORTFOLIO_CARDS.slice(0,2).map(card => (
                <div key={card.title} className="lp-portfolio-col">
                  <div className="lp-port-item lp-reveal">
                    <div className="lp-port-media">
                      <div style={{ position: 'absolute', inset: 0, background: card.color }} />
                      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 16, padding: 40 }}>
                        <div style={{ width: 64, height: 64, background: 'rgba(255,255,255,.08)', borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28 }}>📄</div>
                        <div style={{ font: '600 24px/1.2 Plus Jakarta Sans', color: '#fff', textAlign: 'center' }}>{card.title}</div>
                        <div style={{ font: '400 13px/1 monospace', color: 'rgba(255,255,255,.5)' }}>{card.sub}</div>
                      </div>
                    </div>
                    <div className="lp-port-glow" />
                    <div className="lp-port-info">
                      <div className="lp-port-info-body">
                        <div className="lp-port-info-title">{card.title}</div>
                        <div className="lp-port-info-sub">{card.sub}</div>
                      </div>
                      <div className="lp-port-link-btn">
                        <svg viewBox="0 0 19 19"><path d="M4 15L15 4M15 4H9M15 4v6" strokeWidth="1.8"/></svg>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="lp-portfolio-row">
              {PORTFOLIO_CARDS.slice(2).map(card => (
                <div key={card.title} className="lp-portfolio-col">
                  <div className="lp-port-item lp-reveal lp-reveal-d1">
                    <div className="lp-port-media">
                      <div style={{ position: 'absolute', inset: 0, background: card.color }} />
                      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 16, padding: 40 }}>
                        <div style={{ width: 64, height: 64, background: 'rgba(255,255,255,.08)', borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28 }}>📄</div>
                        <div style={{ font: '600 24px/1.2 Plus Jakarta Sans', color: '#fff', textAlign: 'center' }}>{card.title}</div>
                        <div style={{ font: '400 13px/1 monospace', color: 'rgba(255,255,255,.5)' }}>{card.sub}</div>
                      </div>
                    </div>
                    <div className="lp-port-glow" />
                    <div className="lp-port-info">
                      <div className="lp-port-info-body">
                        <div className="lp-port-info-title">{card.title}</div>
                        <div className="lp-port-info-sub">{card.sub}</div>
                      </div>
                      <div className="lp-port-link-btn">
                        <svg viewBox="0 0 19 19"><path d="M4 15L15 4M15 4H9M15 4v6" strokeWidth="1.8"/></svg>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA BANNER ── */}
      <section className="lp-banner">
        <div className="lp-container" style={{ width: '100%' }}>
          <div className="lp-banner-display">
            <div className="lp-banner-marquee">
              <div className="lp-banner-blk">
                {[0,1].map(i => (
                  <div key={i} className="lp-banner-blk-track">
                    {Array.from({length:8}).map((_,j) => <div key={j} className="lp-banner-blk-item" />)}
                  </div>
                ))}
              </div>
            </div>
            <div className="lp-banner-text lp-reveal">
              Start for free.<br/>
              <span>No card. No setup.</span>
              <div style={{ marginTop: 32, display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
                <Link to="/register" style={{ padding: '14px 36px', background: '#2b2d40', borderRadius: 21, font: '500 16px/1 Inter', color: '#fff', position: 'relative', zIndex: 3 }}>
                  Create Account
                </Link>
                <Link to="#try-it" style={{ padding: '14px 36px', background: 'rgba(0,0,0,.1)', borderRadius: 21, font: '500 16px/1 Inter', color: '#2b2d40', border: '1px solid rgba(0,0,0,.15)', position: 'relative', zIndex: 3 }}>
                  Try as Guest
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="lp-footer">
        <div className="lp-container">
          <div className="lp-footer-inner">
            <div style={{ flex: '0 0 300px' }}>
              <div className="lp-footer-logo">WEAVER</div>
              <div className="lp-footer-tagline">AI-Driven Adaptive Cryptographic Policy Engine</div>
              <Link to="/register" className="lp-footer-cta">
                <span>Get Started →</span>
              </Link>
            </div>
            <div style={{ flex: 1 }}>
              <div className="lp-footer-head">
                Let's secure your data together.
              </div>
              <div className="lp-footer-sub">Automated classification, intelligent encryption, secure sharing.</div>
            </div>
            <div className="lp-footer-nav-col">
              <div className="lp-footer-nav-title">Features</div>
              {['Classify','Encrypt','Share','Dashboard','Admin'].map(l => (
                <div key={l} className="lp-footer-nav-link">{l}</div>
              ))}
            </div>
            <div className="lp-footer-nav-col">
              <div className="lp-footer-nav-title">Account</div>
              {[['Sign In','/login'],['Register','/register']].map(([l,h]) => (
                <Link key={l} to={h} className="lp-footer-nav-link">{l}</Link>
              ))}
            </div>
          </div>
          <div className="lp-footer-bottom">
            <span>© 2025 Weaver · MTech Cyber Security Project</span>
            <button className="lp-footer-scroll" onClick={scrollTop}>
              Back to top
              <svg viewBox="0 0 14 14"><path d="M7 12V2M2 7l5-5 5 5" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </button>
          </div>
        </div>
      </footer>

    </div>
  );
}
