'use client'

import { useState } from 'react'

type Row = {
  domain: string
  threat_type: string
  severity: string
  first_seen: string
  source: string
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
}

type SortKey = keyof Row
const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'domain', label: 'Domain' },
  { key: 'threat_type', label: 'Threat Type' },
  { key: 'severity', label: 'Severity' },
  { key: 'first_seen', label: 'First Seen' },
  { key: 'source', label: 'Source' },
]

export default function ThreatTable({ rows }: { rows: Row[] }) {
  const [sortKey, setSortKey] = useState<SortKey>('first_seen')
  const [sortAsc, setSortAsc] = useState(false)

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(true) }
  }

  const sorted = [...rows].sort((a, b) => {
    const cmp = a[sortKey].localeCompare(b[sortKey])
    return sortAsc ? cmp : -cmp
  })

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800">
            {COLUMNS.map(({ key, label }) => (
              <th
                key={key}
                onClick={() => toggleSort(key)}
                className="text-left px-6 py-3 text-slate-500 font-medium cursor-pointer hover:text-slate-300 transition-colors select-none"
              >
                {label} {sortKey === key ? (sortAsc ? '↑' : '↓') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
              <td className="px-6 py-3 font-mono text-cyan-400">{row.domain}</td>
              <td className="px-6 py-3 text-slate-300">{row.threat_type}</td>
              <td className="px-6 py-3">
                <span className={`text-xs px-2 py-1 rounded border font-medium capitalize ${SEVERITY_COLORS[row.severity] ?? SEVERITY_COLORS.low}`}>
                  {row.severity}
                </span>
              </td>
              <td className="px-6 py-3 text-slate-500 text-xs">{row.first_seen}</td>
              <td className="px-6 py-3 text-slate-500 font-mono text-xs">{row.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
