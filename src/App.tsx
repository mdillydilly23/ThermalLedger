/**
 * App.tsx — root layout.
 * Two tabs: Dashboard (map + detail panel) and Upload (ESG PDF → report).
 */

import { useState } from 'react'
import { DashboardPage } from './pages/DashboardPage'
import { UploadPage } from './pages/UploadPage'

type Tab = 'dashboard' | 'upload'

const styles: Record<string, React.CSSProperties> = {
  shell: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    background: '#0f1117',
    color: '#e2e8f0',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '24px',
    padding: '0 20px',
    height: '48px',
    background: '#1a1d27',
    borderBottom: '1px solid #2d3148',
    flexShrink: 0,
  },
  logo: {
    fontWeight: 700,
    fontSize: '15px',
    letterSpacing: '0.02em',
    color: '#60a5fa',
  },
  tag: {
    fontSize: '11px',
    color: '#64748b',
    marginLeft: '-16px',
  },
  nav: { display: 'flex', gap: '4px', marginLeft: 'auto' },
  tab: {
    padding: '6px 14px',
    borderRadius: '6px',
    border: 'none',
    cursor: 'pointer',
    fontSize: '13px',
    fontWeight: 500,
    transition: 'background 0.15s',
  },
  content: { flex: 1, overflow: 'hidden' },
}

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard')

  return (
    <div style={styles.shell}>
      <header style={styles.header}>
        <span style={styles.logo}>ThermalLedger</span>
        <span style={styles.tag}>AI Carbon Credit Verifier</span>
        <nav style={styles.nav}>
          {(['dashboard', 'upload'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                ...styles.tab,
                background: tab === t ? '#2d3748' : 'transparent',
                color: tab === t ? '#e2e8f0' : '#94a3b8',
              }}
            >
              {t === 'dashboard' ? '🛰 Dashboard' : '📄 Upload ESG'}
            </button>
          ))}
        </nav>
      </header>
      <div style={styles.content}>
        {tab === 'dashboard' ? <DashboardPage /> : <UploadPage />}
      </div>
    </div>
  )
}
