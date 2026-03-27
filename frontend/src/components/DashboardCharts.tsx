import { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  PieChart, Pie, Cell,
  LineChart, Line,
  AreaChart, Area,
  ResponsiveContainer,
} from 'recharts';

// Color palette
const COLORS = {
  primary: '#6366f1',
  secondary: '#8b5cf6',
  success: '#22c55e',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#3b82f6',
};

const SENSITIVITY_COLORS = {
  public: '#22c55e',
  internal: '#3b82f6',
  confidential: '#f59e0b',
  highly_sensitive: '#ef4444',
};

interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}

export function ChartCard({ title, subtitle, children, action }: ChartCardProps) {
  return (
    <div className="card" style={{ padding: '1.5rem', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>{title}</h3>
          {subtitle && <p style={{ margin: '0.25rem 0 0', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

interface SensitivityPieChartProps {
  data: {
    public: number;
    internal: number;
    confidential: number;
    highly_sensitive: number;
  };
}

export function SensitivityPieChart({ data }: SensitivityPieChartProps) {
  const chartData = useMemo(() => [
    { name: 'Public', value: data.public, color: SENSITIVITY_COLORS.public },
    { name: 'Internal', value: data.internal, color: SENSITIVITY_COLORS.internal },
    { name: 'Confidential', value: data.confidential, color: SENSITIVITY_COLORS.confidential },
    { name: 'Restricted', value: data.highly_sensitive, color: SENSITIVITY_COLORS.highly_sensitive },
  ].filter(d => d.value > 0), [data]);

  const total = chartData.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
        No classification data yet
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={2}
          dataKey="value"
          label={({ name, percent }) => `${name} ${percent ? (percent * 100).toFixed(0) : 0}%`}
          labelLine={false}
        >
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip formatter={(value) => [value as number, 'Count']} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

interface ActivityBarChartProps {
  data: Array<{
    date: string;
    day: string;
    classifications: number;
    encryptions: number;
  }>;
}

export function ActivityBarChart({ data }: ActivityBarChartProps) {
  if (!data.length) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
        No activity data yet
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis dataKey="day" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Legend />
        <Bar dataKey="classifications" name="Classifications" fill={COLORS.primary} radius={[4, 4, 0, 0]} />
        <Bar dataKey="encryptions" name="Encryptions" fill={COLORS.secondary} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

interface TrendLineChartProps {
  data: Array<{
    date: string;
    value: number;
    [key: string]: string | number;
  }>;
  dataKey?: string;
  color?: string;
  showArea?: boolean;
}

export function TrendLineChart({ data, dataKey = 'value', color = COLORS.primary, showArea = false }: TrendLineChartProps) {
  if (!data.length) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
        No trend data yet
      </div>
    );
  }

  const Chart = showArea ? AreaChart : LineChart;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <Chart data={data}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        {showArea ? (
          <Area type="monotone" dataKey={dataKey} stroke={color} fill={color} fillOpacity={0.2} />
        ) : (
          <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} />
        )}
      </Chart>
    </ResponsiveContainer>
  );
}

interface StatCardProps {
  title: string;
  value: number | string;
  change?: number;
  changeLabel?: string;
  icon?: React.ReactNode;
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'info';
}

export function StatCard({ title, value, change, changeLabel, icon, color = 'primary' }: StatCardProps) {
  const colorValue = COLORS[color];
  const isPositive = change && change >= 0;

  return (
    <div className="card" style={{ padding: '1.25rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{title}</p>
          <p style={{ margin: '0.5rem 0 0', fontSize: '1.75rem', fontWeight: 700, color: colorValue }}>{value}</p>
          {change !== undefined && (
            <p style={{ 
              margin: '0.25rem 0 0', 
              fontSize: '0.75rem', 
              color: isPositive ? COLORS.success : COLORS.danger 
            }}>
              {isPositive ? '↑' : '↓'} {Math.abs(change)}% {changeLabel || 'vs last week'}
            </p>
          )}
        </div>
        {icon && (
          <div style={{ 
            padding: '0.75rem', 
            borderRadius: '0.5rem', 
            backgroundColor: `${colorValue}15`,
            color: colorValue
          }}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

interface UsageTableProps {
  data: Array<{ algorithm: string; count: number }>;
}

export function UsageTable({ data }: UsageTableProps) {
  const total = data.reduce((sum, d) => sum + d.count, 0);

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="data-table" style={{ width: '100%' }}>
        <thead>
          <tr>
            <th>Algorithm</th>
            <th>Usage</th>
            <th>%</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i}>
              <td><code>{row.algorithm}</code></td>
              <td>{row.count}</td>
              <td>{total ? ((row.count / total) * 100).toFixed(1) : 0}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export { COLORS, SENSITIVITY_COLORS };
