import { useState } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';

const toc = [
  { n: '01', title: 'Getting Started' },
  { n: '02', title: 'Sensitivity Levels' },
  { n: '03', title: 'Cryptographic Policies' },
  { n: '04', title: 'Understanding Explanations (XAI)' },
  { n: '05', title: 'Frequently Asked Questions' },
];

const levels = [
  { level: 'public', color: 'var(--accent-green)', desc: 'Publicly available, non-sensitive content', examples: 'News, press releases', crypto: 'None (SHA-256)' },
  { level: 'internal', color: 'var(--accent-blue)', desc: 'Internal business information', examples: 'Meeting notes, memos', crypto: 'AES-128-GCM' },
  { level: 'confidential', color: 'var(--accent-amber)', desc: 'Contains regulated PII or financial data', examples: 'Employee records, salary data', crypto: 'AES-256-GCM + ECDSA' },
  { level: 'highly_sensitive', color: 'var(--accent-red)', desc: 'Highly sensitive personal or security data', examples: 'Medical records, credentials', crypto: 'AES-256-GCM + RSA-PSS' },
];

const faqs = [
  { q: 'How is my data protected?', a: 'All content is encrypted using AES-256-GCM with keys derived via PBKDF2. The cryptographic parameters are selected automatically based on the classified sensitivity level.' },
  { q: 'What is LIME / SHAP?', a: 'LIME (Local Interpretable Model-agnostic Explanations) shows which words in your content drove the classification decision. SHAP provides global model understanding.' },
  { q: 'Can I override the classification?', a: 'The system provides a recommended classification, but you can manually select a different policy tier before encryption.' },
  { q: 'Who can access my encrypted data?', a: 'Only you and anyone you explicitly share a link with. Share links can be password-protected and time-limited.' },
  { q: 'Is this system open source?', a: 'Weaver is an academic research project. The architecture and implementation methodology are documented in the accompanying thesis.' },
];

export default function HelpPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div style={{ maxWidth: 720, display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 500, color: 'var(--text-primary)' }}>Documentation</h1>
        <p style={{ fontSize: 14, color: 'var(--text-muted)', marginTop: 8 }}>Learn how Weaver's cryptographic policy pipeline works.</p>
      </div>

      {/* TOC */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {toc.map(({ n, title }) => (
          <div key={n} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: 'var(--accent-blue)' }}>{n}</span>
            <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{title}</span>
          </div>
        ))}
      </div>

      {/* Getting started */}
      <div className="card" style={{ padding: 24 }}>
        <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>Getting Started</div>
        <div style={{ height: 1, background: 'var(--border-subtle)', margin: '16px 0' }} />
        {[
          { n: '1', title: 'Paste or upload your content', desc: 'Navigate to Classify & Encrypt and enter text or upload a file.' },
          { n: '2', title: 'Review the classification', desc: 'The ML classifier will assign a sensitivity level and explain the decision.' },
          { n: '3', title: 'Encrypt and share', desc: 'One click encrypts with the matched policy. Create a share link for external access.' },
        ].map(({ n, title, desc }) => (
          <div key={n} style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: 'var(--accent-blue)', flexShrink: 0 }}>{n}</span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{title}</div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginTop: 4 }}>{desc}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Sensitivity levels table */}
      <div className="card" style={{ padding: 24 }}>
        <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>Sensitivity Levels</div>
        <div style={{ height: 1, background: 'var(--border-subtle)', margin: '16px 0' }} />
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--bg-primary)' }}>
              {['LEVEL', 'DESCRIPTION', 'EXAMPLES', 'CRYPTO TIER'].map(h => (
                <th key={h} style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-muted)', padding: '8px 12px', textAlign: 'left' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {levels.map(({ level, color, desc, examples, crypto }) => (
              <tr key={level} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color, padding: '10px 12px' }}>{level}</td>
                <td style={{ fontSize: 13, color: 'var(--text-secondary)', padding: '10px 12px' }}>{desc}</td>
                <td style={{ fontSize: 13, color: 'var(--text-muted)', padding: '10px 12px' }}>{examples}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-primary)', padding: '10px 12px' }}>{crypto}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* FAQ */}
      <div className="card" style={{ padding: 24 }}>
        <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--text-primary)' }}>Frequently Asked Questions</div>
        <div style={{ height: 1, background: 'var(--border-subtle)', margin: '16px 0' }} />
        {faqs.map((faq, i) => (
          <div key={i} className="accordion-item">
            <button className="accordion-trigger" onClick={() => setOpenFaq(openFaq === i ? null : i)}>
              <span>{faq.q}</span>
              {openFaq === i ? <ChevronDown size={12} color="var(--text-muted)" /> : <ChevronRight size={12} color="var(--text-muted)" />}
            </button>
            {openFaq === i && (
              <div className="accordion-content">{faq.a}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
