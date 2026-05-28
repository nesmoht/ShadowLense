'use client'

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

const MOCK_STATS = { total: 1284, critical: 47, high: 213, medium: 589 }

const MOCK_CHART = [
  { date: 'May 22', threats: 38 },
  { date: 'May 23', threats: 52 },
  { date: 'May 24', threats: 41 },
  { date: 'May 25', threats: 67 },
  { date: 'May 26', threats: 89 },
  { date: 'May 27', threats: 74 },
  { date: 'May 28', threats: 93 },
]

const MOCK_ALERTS = [
  { id: 1, domain: 'contoso.com', type: 'Credential Leak', severity: 'critical', source: 'paste-site-darkweb', detected: '2026-05-28 14:32' },
  { id: 2, domain: 'fabrikam.io', type: 'Ransomware IOC', severity: 'high', source: 'ahmia-search', detected: '2026-05-28 11:17' },
  { id: 3, domain: 'northwind.net', type: 'C2 Infrastructure', severity: 'high', source: 'urlhaus-api', detected: '2026-05-27 22:05' },
  { id: 4, domain: 'contoso.com', type: 'Data Exfiltration', severity: 'medium', source: 'malware-bazaar', detected: '2026-05-27 18:41' },
  { id: 5, domain: 'adventure-works.com', type: 'Phishing Kit', severity: 'medium', source: 'paste-site-darkweb', detected: '2026-05-27 09:12' },
]

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <p className="text-slate-500 text-sm mb-1">{label}</p>
      <p className={`text-3xl font-bold ${color}`}>{value.toLocaleString()}</p>
    </div>
  )
}

export default function Dashboard() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Threat Dashboard</h1>
        <p className="text-slate-500 text-sm mt-1">Live view of detected threats across monitored domains</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Threats" value={MOCK_STATS.total} color="text-cyan-400" />
        <StatCard label="Critical" value={MOCK_STATS.critical} color="text-red-400" />
        <StatCard label="High" value={MOCK_STATS.high} color="text-orange-400" />
        <StatCard label="Medium" value={MOCK_STATS.medium} color="text-yellow-400" />
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 className="text-sm font-medium text-slate-400 mb-4">Threats Detected — Last 7 Days</h2>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={MOCK_CHART}>
            <defs>
              <linearGradient id="cyan" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 8 }}
              labelStyle={{ color: '#94a3b8' }}
              itemStyle={{ color: '#22d3ee' }}
            />
            <Area type="monotone" dataKey="threats" stroke="#22d3ee" strokeWidth={2} fill="url(#cyan)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl">
        <div className="px-6 py-4 border-b border-slate-800">
          <h2 className="text-sm font-medium text-slate-400">Recent Alerts</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="text-left px-6 py-3 text-slate-500 font-medium">Domain</th>
                <th className="text-left px-6 py-3 text-slate-500 font-medium">Threat Type</th>
                <th className="text-left px-6 py-3 text-slate-500 font-medium">Severity</th>
                <th className="text-left px-6 py-3 text-slate-500 font-medium">Source</th>
                <th className="text-left px-6 py-3 text-slate-500 font-medium">Detected</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_ALERTS.map((a) => (
                <tr key={a.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                  <td className="px-6 py-3 font-mono text-cyan-400">{a.domain}</td>
                  <td className="px-6 py-3 text-slate-300">{a.type}</td>
                  <td className="px-6 py-3">
                    <span className={`text-xs px-2 py-1 rounded border font-medium capitalize ${SEVERITY_COLORS[a.severity]}`}>
                      {a.severity}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-slate-500 font-mono text-xs">{a.source}</td>
                  <td className="px-6 py-3 text-slate-500 text-xs">{a.detected}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
