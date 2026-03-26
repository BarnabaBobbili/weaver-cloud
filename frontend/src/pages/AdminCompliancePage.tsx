import { useEffect, useState } from 'react';

import { adminApi } from '../api';
import type { ComplianceReport } from '../types';

export default function AdminCompliancePage() {
  const [report, setReport] = useState<ComplianceReport | null>(null);

  useEffect(() => {
    adminApi.complianceReport().then((res) => setReport(res.data)).catch(() => {});
  }, []);

  const downloadCsv = () => {
    if (!report) return;
    const lines = [
      ['metric', 'value'],
      ['total_encryptions', String(report.total_encryptions)],
      ['unencrypted_ops', String(report.unencrypted_ops)],
      ['mfa_adoption_pct', String(report.mfa_adoption_pct)],
      ['locked_accounts', String(report.locked_accounts)],
      ['policy_violations', String(report.policy_violations)],
      ['security_score', String(report.security_score)],
    ];
    const blob = new Blob([lines.map((line) => line.join(',')).join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'compliance-report.csv';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="row-between">
        <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>System-wide compliance summary</span>
        <button className="btn btn-primary btn-sm" onClick={downloadCsv} disabled={!report}>Download CSV</button>
      </div>
      <div className="grid-4">
        {[
          ['Total Encryptions', report?.total_encryptions ?? 0],
          ['Unencrypted Ops', report?.unencrypted_ops ?? 0],
          ['MFA Adoption %', report?.mfa_adoption_pct ?? 0],
          ['Security Score', report?.security_score ?? 0],
        ].map(([label, value]) => (
          <div key={label} className="stat-block">
            <div className="stat-label">{label}</div>
            <div className="stat-value">{Number(value).toLocaleString()}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card" style={{ padding: 24 }}>
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>Encryption Coverage</div>
          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {Object.entries(report?.encryptions_by_level || {}).map(([level, count]) => (
              <div key={level} className="row-between">
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{level.replace('_', ' ')}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card" style={{ padding: 24 }}>
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>Policy Violations</div>
          <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Override events</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{report?.policy_violations ?? 0}</span>
            </div>
            <div className="row-between">
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Locked accounts</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{report?.locked_accounts ?? 0}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
