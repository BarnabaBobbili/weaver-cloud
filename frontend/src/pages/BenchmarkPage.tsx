import { useEffect, useMemo, useState } from 'react';

import { benchmarkApi } from '../api';
import type { BenchmarkResult } from '../types';
import { getApiErrorMessage } from '../utils/apiError';
import { formatDateTime } from '../utils/formatters';

const CAT_COLOR: Record<BenchmarkResult['category'], string> = {
  Symmetric: 'var(--accent-blue)',
  Asymmetric: 'var(--accent-amber)',
  KDF: 'var(--text-muted)',
  Hash: 'var(--accent-green)',
};

export default function BenchmarkPage() {
  const [results, setResults] = useState<BenchmarkResult[]>([]);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [lastRun, setLastRun] = useState<string | null>(null);
  const [message, setMessage] = useState('Loading benchmark state...');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await benchmarkApi.results();
        if (cancelled) return;

        setResults(res.data.results);
        setMessage(res.data.results.length > 0 ? '' : res.data.message || 'Run a benchmark to generate live measurements.');
      } catch (err) {
        if (!cancelled) {
          setResults([]);
          setMessage('');
          setError(getApiErrorMessage(err, 'Benchmark data is unavailable.'));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleRun = async () => {
    setRunning(true);
    setError('');
    try {
      const res = await benchmarkApi.run();
      setResults(res.data.results);
      setMessage(res.data.results.length > 0 ? '' : 'No benchmark results were returned.');
      setLastRun(new Date().toISOString());
    } catch (err) {
      setError(getApiErrorMessage(err, 'Benchmark execution failed.'));
    } finally {
      setRunning(false);
    }
  };

  const fastestByCategory = useMemo(() => {
    const fastest: Partial<Record<BenchmarkResult['category'], number>> = {};
    for (const row of results) {
      const current = fastest[row.category];
      fastest[row.category] = current === undefined ? row.time_ms : Math.min(current, row.time_ms);
    }
    return fastest;
  }, [results]);

  const chartBars = useMemo(() => {
    return results
      .filter((result) => result.throughput_mbs !== undefined && result.throughput_mbs > 0)
      .sort((left, right) => (right.throughput_mbs || 0) - (left.throughput_mbs || 0))
      .slice(0, 6)
      .map((result) => ({
        label: `${result.algorithm} ${result.operation}`,
        val: result.throughput_mbs || 0,
        color: CAT_COLOR[result.category],
      }));
  }, [results]);

  const maxBar = Math.max(1, ...chartBars.map((bar) => bar.val));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div className="row-between" style={{ gap: 16, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Compare live cryptographic algorithm performance on this backend instance.</span>
        <button className="btn btn-primary" style={{ width: 170, height: 38 }} onClick={() => void handleRun()} disabled={running}>
          {running ? 'Running…' : 'Run Benchmarks'}
        </button>
      </div>

      {(error || message) && (
        <div style={{
          padding: '10px 14px',
          background: error ? 'rgba(181,74,74,0.1)' : 'var(--bg-primary)',
          border: `1px solid ${error ? 'var(--accent-red)' : 'var(--border-subtle)'}`,
          borderRadius: 2,
          fontSize: 13,
          color: error ? 'var(--accent-red)' : 'var(--text-muted)',
        }}>
          {error || message}
        </div>
      )}

      <div className="card">
        <div className="row-between" style={{ padding: '20px 20px 0', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>Benchmark Results</span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Last run: {lastRun ? formatDateTime(lastRun) : loading ? 'Loading…' : 'Not run in this session'}
          </span>
        </div>
        <table className="data-table" style={{ marginTop: 0 }}>
          <thead>
            <tr>{['ALGORITHM', 'OPERATION', 'DATA SIZE', 'TIME (ms)', 'THROUGHPUT (MB/s)', 'CATEGORY'].map((heading) => <th key={heading}>{heading}</th>)}</tr>
          </thead>
          <tbody>
            {results.length > 0 ? results.map((row) => {
              const isFastest = fastestByCategory[row.category] === row.time_ms;
              return (
                <tr key={`${row.algorithm}-${row.operation}-${row.category}`}>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{row.algorithm}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{row.operation}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{row.data_size}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: isFastest ? 'var(--accent-green)' : 'var(--text-primary)', fontWeight: isFastest ? 500 : 400 }}>
                    {row.time_ms.toFixed(2)}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: row.throughput_mbs ? 'var(--text-primary)' : 'var(--text-dim)' }}>
                    {row.throughput_mbs !== undefined ? row.throughput_mbs.toFixed(4) : '—'}
                  </td>
                  <td>
                    <span className="badge" style={{ color: CAT_COLOR[row.category], borderColor: CAT_COLOR[row.category], fontSize: 11 }}>
                      {row.category}
                    </span>
                  </td>
                </tr>
              );
            }) : (
              <tr>
                <td colSpan={6} style={{ color: 'var(--text-muted)' }}>
                  {loading ? 'Loading benchmark results...' : 'No live benchmark results yet.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ padding: 24 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 16 }}>Throughput Comparison</div>
        {chartBars.length > 0 ? (
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, minHeight: 200, paddingBottom: 24, position: 'relative' }}>
            {chartBars.map(({ label, val, color }) => {
              const height = (val / maxBar) * 180;
              return (
                <div key={label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color, marginBottom: 4 }}>{val.toFixed(4)} MB/s</span>
                  <div style={{ width: 42, height, background: color, borderRadius: '2px 2px 0 0' }} />
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', textAlign: 'center', maxWidth: 84 }}>{label}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            Run the benchmark suite to populate throughput comparisons.
          </div>
        )}
      </div>
    </div>
  );
}
