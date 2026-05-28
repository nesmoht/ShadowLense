'use client'

import { useState } from 'react'
import ThreatTable from '@/components/ThreatTable'

const MOCK_RESULTS: Record<string, any[]> = {
  'contoso.com': [
    { domain: 'contoso.com', threat_type: 'Credential Leak', severity: 'critical', first_seen: '2026-05-28', source: 'paste-site-darkweb' },
    { domain: 'contoso.com', threat_type: 'Data Exfiltration', severity: 'medium', first_seen: '2026-05-27', source: 'malware-bazaar' },
  ],
  'fabrikam.io': [
    { domain: 'fabrikam.io', threat_type: 'Ransomware IOC', severity: 'high', first_seen: '2026-05-28', source: 'ahmia-search' },
  ],
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<any[] | null>(null)
  const [searched, setSearched] = useState(false)

  function handleSearch() {
    const q = query.trim().toLowerCase()
    const found = MOCK_RESULTS[q] ?? []
    setResults(found)
    setSearched(true)
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Domain Search</h1>
        <p className="text-slate-500 text-sm mt-1">Search the Gold layer for threats targeting a specific domain</p>
      </div>

      <div className="flex gap-3 max-w-xl">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="contoso.com"
          className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500 font-mono"
        />
        <button
          onClick={handleSearch}
          className="px-5 py-2.5 bg-cyan-500 hover:bg-cyan-400 text-slate-900 font-semibold text-sm rounded-lg transition-colors"
        >
          Search
        </button>
      </div>

      {searched && (
        results && results.length > 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-xl">
            <div className="px-6 py-4 border-b border-slate-800">
              <p className="text-sm text-slate-400">{results.length} threat{results.length !== 1 ? 's' : ''} found for <span className="text-cyan-400 font-mono">{query}</span></p>
            </div>
            <ThreatTable rows={results} />
          </div>
        ) : (
          <div className="bg-slate-900 border border-slate-800 rounded-xl px-6 py-10 text-center">
            <p className="text-slate-500 text-sm">No threats found for <span className="text-slate-300 font-mono">{query}</span></p>
            <p className="text-slate-600 text-xs mt-1">This domain has not appeared in any monitored sources.</p>
          </div>
        )
      )}
    </div>
  )
}
