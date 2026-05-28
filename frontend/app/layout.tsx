import type { Metadata } from 'next'
import Link from 'next/link'
import './globals.css'

export const metadata: Metadata = {
  title: 'ShadowLense — Dark Web Threat Intelligence',
  description: 'Open source dark web threat intelligence monitor',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#020817] text-slate-200">
        <header className="border-b border-slate-800 bg-[#0a1628]">
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center">
                <span className="text-cyan-400 text-sm font-bold">SL</span>
              </div>
              <span className="text-lg font-semibold text-white tracking-tight">ShadowLense</span>
              <span className="text-xs text-slate-500 hidden sm:block">dark web threat intelligence</span>
            </Link>
            <nav className="flex items-center gap-6 text-sm">
              <Link href="/" className="text-slate-400 hover:text-cyan-400 transition-colors">Dashboard</Link>
              <Link href="/search" className="text-slate-400 hover:text-cyan-400 transition-colors">Search</Link>
            </nav>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-8">
          {children}
        </main>
        <footer className="border-t border-slate-800 mt-16">
          <div className="max-w-7xl mx-auto px-6 py-4 text-xs text-slate-600 flex justify-between">
            <span>ShadowLense — open source threat intelligence</span>
            <span>~$5/month · runs on GitHub Actions</span>
          </div>
        </footer>
      </body>
    </html>
  )
}
