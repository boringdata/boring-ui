import { useState, useCallback, useEffect } from 'react'
import {
  MessageSquare, Plus, Send, Search, Settings, User, Sparkles,
  FileCode, PanelRightOpen, X, Pin, Clock, Grid3X3, List,
  Maximize2, Layers, ChevronDown, ChevronRight, Download,
  BarChart3, Table2, FileText, Image, Code2, Globe,
  PanelRightClose, Eye, FolderOpen,
} from 'lucide-react'

// ─── MOCK DATA ───────────────────────────────────────────────
const SESSIONS = [
  { id: 's1', title: 'Q3 Revenue Analysis', time: '2m', status: 'active' },
  { id: 's2', title: 'Competitor Research', time: '1h', status: 'paused' },
  { id: 's3', title: 'Fix auth bug', time: '3h', status: 'idle' },
]

const CHAT_MESSAGES = {
  s1: [
    { role: 'user', text: 'Can you analyze Q3 revenue by region and compare with Q4 projections?' },
    { role: 'agent', text: 'I\'ve pulled the revenue data and created a comparison chart. Q4 projections show a 22% increase driven primarily by enterprise renewals.', artifact: 'chart-q3q4' },
    { role: 'user', text: 'Show me the raw data as well' },
    { role: 'agent', text: 'Here\'s the full dataset. APAC is the fastest growing region at 34% YoY.', artifact: 'table-revenue' },
    { role: 'user', text: 'Also pull up last quarter\'s board deck for reference' },
    { role: 'agent', text: 'I found the Q3 board presentation in your Drive.', artifact: 'pdf-board-deck' },
  ],
  s2: [
    { role: 'user', text: 'Research Acme Corp — pull their 10-K and summarize their pricing strategy' },
    { role: 'agent', text: 'I\'ve analyzed Acme Corp\'s public filings and built a pricing comparison matrix.', artifact: 'table-pricing' },
    { role: 'agent', text: 'Here\'s the competitive positioning map I generated.', artifact: 'chart-positioning' },
  ],
  s3: [
    { role: 'user', text: 'The token refresh is broken. Users get logged out after 30 minutes.' },
    { role: 'agent', text: 'Found it. The login function in auth.js never sets up a refresh interval. Here\'s the fix.', artifact: 'code-auth' },
  ],
}

const ARTIFACTS = {
  'chart-q3q4': { id: 'chart-q3q4', type: 'chart', title: 'Q3 vs Q4 Revenue', icon: BarChart3, color: '#3b82f6', category: 'Data' },
  'table-revenue': { id: 'table-revenue', type: 'table', title: 'Revenue by Region', icon: Table2, color: '#22c55e', category: 'Data' },
  'pdf-board-deck': { id: 'pdf-board-deck', type: 'document', title: 'Q3 Board Deck.pdf', icon: FileText, color: '#f59e0b', category: 'Documents' },
  'table-pricing': { id: 'table-pricing', type: 'table', title: 'Pricing Matrix', icon: Table2, color: '#22c55e', category: 'Data' },
  'chart-positioning': { id: 'chart-positioning', type: 'chart', title: 'Positioning Map', icon: BarChart3, color: '#3b82f6', category: 'Data' },
  'code-auth': { id: 'code-auth', type: 'code', title: 'auth.js — Fix', icon: Code2, color: '#a78bfa', category: 'Code' },
}

const SESSION_ARTIFACTS = {
  s1: ['chart-q3q4', 'table-revenue', 'pdf-board-deck'],
  s2: ['table-pricing', 'chart-positioning'],
  s3: ['code-auth'],
}

// ─── LEFT SIDEBAR ────────────────────────────────────────────
function LeftSidebar({ activeSession, sessions, onSwitchSession }) {
  const [activeTab, setActiveTab] = useState(null) // null=collapsed, 'search'|'history'

  const toggle = (tab) => setActiveTab(prev => prev === tab ? null : tab)

  return (
    <div className="left-bar">
      {/* Icon strip (always visible, 48px) */}
      <nav className="left-icons">
        <div className="rail-brand-icon">B</div>
        <button className="rail-icon-btn rail-new-icon" title="New chat (⌘N)"><Plus size={16} /></button>
        <div className="rail-sep" />
        <button className={`rail-icon-btn${activeTab === 'history' ? ' active' : ''}`}
          onClick={() => toggle('history')} title="Session history">
          <Clock size={17} />
        </button>
        <div className="rail-spacer" />
        <div className="rail-sep" />
        <button className="rail-icon-btn" title="Settings"><Settings size={17} /></button>
        <button className="rail-icon-btn" title="Profile"><User size={17} /></button>
      </nav>

      {/* Expandable panel (shows when a tab is active) */}
      {activeTab && (
        <div className="left-panel">
          {activeTab === 'history' && (
            <>
              <div className="left-panel-head">History</div>
              <div className="rail-sessions">
                <div className="rail-sessions-group">
                  <div className="rail-sessions-date">Today</div>
                  {sessions.filter(s => s.status !== 'idle' || s.time.includes('h')).map(s => (
                    <button key={s.id} className={`rail-btn${s.id === activeSession ? ' active' : ''}`}
                      onClick={() => onSwitchSession(s.id)}>
                      <span className={`rail-session-dot ${s.status}`} />
                      <span className="rail-btn-label">{s.title}</span>
                      <span className="rail-btn-meta">{s.time}</span>
                    </button>
                  ))}
                </div>
                <div className="rail-sessions-group">
                  <div className="rail-sessions-date">Yesterday</div>
                  {sessions.filter(s => s.status === 'idle' && !s.time.includes('h')).map(s => (
                    <button key={s.id} className={`rail-btn${s.id === activeSession ? ' active' : ''}`}
                      onClick={() => onSwitchSession(s.id)}>
                      <span className={`rail-session-dot ${s.status}`} />
                      <span className="rail-btn-label">{s.title}</span>
                      <span className="rail-btn-meta">{s.time}</span>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ─── CHAT ────────────────────────────────────────────────────
function Chat({ session, onOpenArtifact, openArtifacts, activeArtifact }) {
  const messages = CHAT_MESSAGES[session] || []
  return (
    <div className="center">
      <div className="chat-scroll">
        <div className="chat-msgs">
          {messages.length === 0 && (
            <div className="empty" style={{ flex: 1 }}>
              <Sparkles size={32} style={{ opacity: 0.15 }} />
              <span style={{ fontSize: 15 }}>What can I help with?</span>
              <span style={{ fontSize: 12 }}>Results appear on the Surface →</span>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className="chat-msg">
              <div className="chat-role">
                <div style={{ width: 20, height: 20, borderRadius: 4, background: m.role === 'user' ? 'var(--bg-elevated)' : 'var(--accent-dim)', color: m.role === 'user' ? 'var(--text-secondary)' : 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border-subtle)', flexShrink: 0 }}>
                  {m.role === 'user' ? <User size={11} /> : <Sparkles size={11} />}
                </div>
                {m.role === 'user' ? 'You' : 'Agent'}
              </div>
              <span className="chat-text">{m.text}</span>
              {m.artifact && ARTIFACTS[m.artifact] && (() => {
                const a = ARTIFACTS[m.artifact]
                const Icon = a.icon
                const isActive = m.artifact === activeArtifact
                const isOpen = openArtifacts.includes(m.artifact)
                return (
                  <div className={`chat-artifact${isActive ? ' active' : isOpen ? ' open' : ''}`}
                    onClick={() => onOpenArtifact(m.artifact)}>
                    <div className="chat-artifact-icon" style={{ color: a.color }}><Icon size={16} /></div>
                    <div className="chat-artifact-info">
                      <span className="chat-artifact-title">{a.title}</span>
                      <span className="chat-artifact-type">{a.type}</span>
                    </div>
                    <div style={{ flex: 1 }} />
                    <ChevronRight size={14} style={{ color: 'var(--text-tertiary)', opacity: isActive ? 1 : 0.4, transition: 'opacity 0.2s', flexShrink: 0 }} />
                  </div>
                )
              })()}
            </div>
          ))}
        </div>
      </div>
      <div className="chat-input-wrap">
        <div className="chat-input">
          <input placeholder="Ask a question..." />
          <div style={{ display: 'flex', gap: 4, marginRight: 4, flexShrink: 0 }}>
            <kbd style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', padding: '2px 6px', borderRadius: 4, fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', boxShadow: '0 1px 1px rgba(0,0,0,0.2)' }}>⌘</kbd>
            <kbd style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)', padding: '2px 6px', borderRadius: 4, fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', boxShadow: '0 1px 1px rgba(0,0,0,0.2)' }}>K</kbd>
          </div>
          <button className="chat-send"><Send size={16} /></button>
        </div>
      </div>
    </div>
  )
}

// ─── ARTIFACT RENDERERS (polymorphic) ────────────────────────
function ChartRenderer() {
  return (
    <div className="r-chart">
      <div className="r-chart-bars">
        {[{ l: 'NA', a: 82, b: 95 }, { l: 'EMEA', a: 64, b: 78 }, { l: 'APAC', a: 45, b: 68 }, { l: 'LATAM', a: 28, b: 35 }].map(d => (
          <div key={d.l} className="r-chart-group">
            <div className="r-chart-pair">
              <div className="r-chart-bar q3" style={{ height: `${d.a}%` }}><span>{d.a}k</span></div>
              <div className="r-chart-bar q4" style={{ height: `${d.b}%` }}><span>{d.b}k</span></div>
            </div>
            <span className="r-chart-label">{d.l}</span>
          </div>
        ))}
      </div>
      <div className="r-chart-legend">
        <span><span className="dot q3" /> Q3 Actual</span>
        <span><span className="dot q4" /> Q4 Projected</span>
      </div>
      <p className="r-chart-note">Q4 projections show +22% overall. APAC fastest growing at +51%.</p>
    </div>
  )
}

function TableRenderer({ pricing }) {
  const headers = pricing
    ? ['Tier', 'Acme', 'Ours', 'Delta']
    : ['Region', 'Q3', 'Q4 Proj', 'YoY']
  const rows = pricing
    ? [['Starter','$99','$79','-$20'],['Pro','$299','$249','-$50'],['Enterprise','$999','$850','-$149'],['Enterprise+','$2.5k','$2k','-$500']]
    : [['North America','$82M','$95M','+15%'],['EMEA','$64M','$79M','+23%'],['APAC','$45M','$68M','+51%'],['LATAM','$29M','$35M','+23%']]
  return (
    <div className="r-table">
      <table>
        <thead><tr>{headers.map(h => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>{rows.map((r,i) => <tr key={i}>{r.map((c,j) => <td key={j} className={j===3?'cell-accent':''}>{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

function DocumentRenderer() {
  return (
    <div className="r-doc">
      <div className="r-doc-page">
        <h2>Q3 2026 Board Presentation</h2>
        <p className="r-doc-sub">Confidential — For Board Members Only</p>
        <hr />
        <h3>Executive Summary</h3>
        <p>Total revenue reached $220.4M in Q3, representing 18% year-over-year growth.
        Enterprise segment continues to drive expansion with ACV increasing 34% to $285K.</p>
        <h3>Key Highlights</h3>
        <ul>
          <li>APAC expansion exceeded targets by 40%</li>
          <li>New product line contributed $18M in first full quarter</li>
          <li>Gross margins improved 200bps to 78%</li>
          <li>12 enterprise deals closed above $500K</li>
        </ul>
        <div className="r-doc-pagenum">Page 1 of 24</div>
      </div>
    </div>
  )
}

function CodeRenderer() {
  const lines = [
    { n: 1, c: "import jwt from 'jsonwebtoken'" },
    { n: 2, c: "import { refreshToken } from './refresh'" },
    { n: 3, c: '' },
    { n: 4, c: 'export async function login(email, pw) {' },
    { n: 5, c: '  const res = await fetch(\'/api/auth\', { ... })' },
    { n: 6, c: '  const { token, user } = await res.json()', d: '-' },
    { n: 6, c: '  const { token, refreshTok, user } = await res.json()', d: '+' },
    { n: 7, c: '  scheduleRefresh(refreshTok, token)', d: '+' },
    { n: 8, c: '  return { token, user }' },
    { n: 9, c: '}' },
  ]
  return (
    <div className="r-code">
      <div className="mock-ed">
        {lines.map((l, i) => (
          <div key={i} className={`mock-ln${l.d === '+' ? ' add' : l.d === '-' ? ' del' : ''}`}>
            <span className="mock-no">{l.d === '-' ? '−' : l.d === '+' ? '+' : l.n}</span>
            <span className="mock-code">{l.c}</span>
          </div>
        ))}
      </div>
      <div className="diff-bar">
        <button className="diff-btn ok">✓ Accept</button>
        <button className="diff-btn no">✕ Reject</button>
      </div>
    </div>
  )
}

function ArtifactRenderer({ id }) {
  if (id === 'chart-q3q4' || id === 'chart-positioning') return <ChartRenderer />
  if (id === 'table-revenue') return <TableRenderer />
  if (id === 'table-pricing') return <TableRenderer pricing />
  if (id === 'pdf-board-deck') return <DocumentRenderer />
  if (id === 'code-auth') return <CodeRenderer />
  return <div className="empty"><span>Unknown artifact</span></div>
}

// ─── THE SURFACE ─────────────────────────────────────────────
function SfResizeHandle({ onResize }) {
  const handleMouseDown = useCallback((e) => {
    e.preventDefault()
    const sf = document.querySelector('.sf')
    const startX = e.clientX
    const startW = sf?.offsetWidth || 620
    const onMove = (ev) => onResize(Math.max(380, Math.min(window.innerWidth * 0.65, startW + (startX - ev.clientX))))
    const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp); document.body.style.cursor = ''; document.body.style.userSelect = '' }
    document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMove); document.addEventListener('mouseup', onUp)
  }, [onResize])
  return <div className="sf-resize" onMouseDown={handleMouseDown} />
}

function Surface({ session, openArtifacts, activeArtifact, onSelect, onClose, collapsed, onToggleCollapse }) {
  const [explorerOpen, setExplorerOpen] = useState(false)

  const sessionArtifacts = SESSION_ARTIFACTS[session] || []
  const allArtifacts = sessionArtifacts.map(id => ARTIFACTS[id]).filter(Boolean)
  const active = ARTIFACTS[activeArtifact]

  // Group by category for explorer
  const groups = {}
  allArtifacts.forEach(a => {
    if (!groups[a.category]) groups[a.category] = []
    groups[a.category].push(a)
  })

  if (collapsed) {
    // Completely hidden when no artifacts — Surface appears only when needed
    if (openArtifacts.length === 0) return null
    return (
      <div className="sf-handle" onClick={onToggleCollapse} title="Open Surface (⌘2)">
        <PanelRightOpen size={14} />
        <span className="sf-handle-count">{openArtifacts.length}</span>
      </div>
    )
  }

  return (
    <>
      <SfResizeHandle onResize={(w) => {
        const el = document.querySelector('.sf')
        if (el) el.style.width = w + 'px'
      }} />
      <div className="sf">
        {/* Explorer sidebar (collapsed by default, toggles open) */}
        <div className={`sf-explorer${explorerOpen ? '' : ' closed'}`}>
          <div className="sf-explorer-head">
            <span>Artifacts</span>
            <span className="sf-explorer-count">{allArtifacts.length}</span>
          </div>
          {allArtifacts.length === 0 ? (
            <div className="sf-explorer-empty">No artifacts yet</div>
          ) : (
            <div className="sf-explorer-list">
              {Object.entries(groups).map(([cat, items]) => (
                <div key={cat} className="sf-explorer-group">
                  <div className="sf-explorer-cat">{cat} <span>{items.length}</span></div>
                  {items.map(a => {
                    const Icon = a.icon
                    const isOpen = openArtifacts.includes(a.id)
                    return (
                      <div key={a.id}
                        className={`sf-explorer-item${a.id === activeArtifact ? ' active' : ''}`}
                        onClick={() => onSelect(a.id)}>
                        <span className="sf-explorer-item-icon" style={{ color: a.color }}><Icon size={13} /></span>
                        <span className="sf-explorer-item-title">{a.title}</span>
                        {isOpen && <span className="sf-explorer-item-dot" />}
                      </div>
                    )
                  })}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Main viewer area */}
        <div className="sf-main">
          {/* Top bar: explorer toggle + tabs + close */}
          <div className="sf-topbar">
            <button className={`sf-explorer-toggle${explorerOpen ? ' active' : ''}`}
              onClick={() => setExplorerOpen(o => !o)}>
              {explorerOpen ? <ChevronDown size={12} style={{ transform: 'rotate(90deg)' }} /> : <ChevronRight size={12} />}
              <FolderOpen size={13} />
              <span>Artifacts</span>
              {allArtifacts.length > 0 && <span className="sf-explorer-toggle-count">{allArtifacts.length}</span>}
            </button>
            <div className="sf-tabs">
              {openArtifacts.map(id => {
                const a = ARTIFACTS[id]; if (!a) return null; const Icon = a.icon
                return (
                  <button key={id} className={`sf-tab${id === activeArtifact ? ' active' : ''}`}
                    onClick={() => onSelect(id)}>
                    <Icon size={11} style={{ color: a.color }} />
                    <span>{a.title}</span>
                    <span className="sf-tab-close" onClick={e => { e.stopPropagation(); onClose(id) }}>
                      <X size={10} />
                    </span>
                  </button>
                )
              })}
            </div>
            <div style={{ flex: 1 }} />
            <button className="sf-viewer-btn" onClick={onToggleCollapse} title="Close Surface (⌘2)">
              <PanelRightClose size={14} />
            </button>
          </div>

          {/* Viewer content */}
          <div className="sf-body">
            {!active ? (
              <div className="sf-empty">
                <div className="sf-empty-icon" style={{ width: 48, height: 48, borderRadius: 12, background: 'linear-gradient(180deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border-subtle)', marginBottom: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.2)' }}>
                  <Sparkles size={20} style={{ color: 'var(--text-secondary)' }} />
                </div>
                <div className="sf-empty-title">The Surface is clear</div>
                <div className="sf-empty-sub">
                  Ask the agent to analyze data, generate charts,<br/>
                  review documents, or write code.
                </div>
                <div className="sf-empty-hints">
                  <span>✨ Generate a dashboard</span>
                  <span>✨ Analyze a spreadsheet</span>
                  <span>✨ Draft a presentation</span>
                </div>
              </div>
            ) : (
              <div className="sf-viewer">
                <div className="sf-viewer-head">
                  <div className="sf-viewer-icon" style={{ color: active.color }}>
                    <active.icon size={16} />
                  </div>
                  <div className="sf-viewer-info">
                    <span className="sf-viewer-title">{active.title}</span>
                    <span className="sf-viewer-type">{active.type}</span>
                  </div>
                  <div style={{ flex: 1 }} />
                  <button className="sf-viewer-btn" title="Export"><Download size={13} /></button>
                </div>
                <div className="sf-viewer-content">
                  <ArtifactRenderer id={activeArtifact} />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

// ─── APP ─────────────────────────────────────────────────────
export default function App() {
  const [activeSession, setActiveSession] = useState('s1')
  const [openArtifacts, setOpenArtifacts] = useState([])
  const [activeArtifact, setActiveArtifact] = useState(null)
  const [surfaceCollapsed, setSurfaceCollapsed] = useState(true) // hidden until first artifact

  const openArtifact = useCallback((id) => {
    setOpenArtifacts(prev => prev.includes(id) ? prev : [...prev, id])
    setActiveArtifact(id)
    setSurfaceCollapsed(false)
  }, [])

  const closeArtifact = useCallback((id) => {
    setOpenArtifacts(prev => {
      const next = prev.filter(a => a !== id)
      if (id === activeArtifact) setActiveArtifact(next[next.length - 1] || null)
      return next
    })
  }, [activeArtifact])

  useEffect(() => {
    const handler = (e) => {
      const mod = e.metaKey || e.ctrlKey
      if (mod && e.key === '2') { e.preventDefault(); setSurfaceCollapsed(c => !c) }
      if (e.key === 'Escape') { document.querySelector('.chat-input input')?.focus() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="app">
      <LeftSidebar activeSession={activeSession} sessions={SESSIONS} onSwitchSession={setActiveSession} />
      <Chat session={activeSession} onOpenArtifact={openArtifact} openArtifacts={openArtifacts} activeArtifact={activeArtifact} />
      <Surface
        session={activeSession}
        openArtifacts={openArtifacts}
        activeArtifact={activeArtifact}
        onSelect={openArtifact}
        onClose={closeArtifact}
        collapsed={surfaceCollapsed}
        onToggleCollapse={() => setSurfaceCollapsed(c => !c)}
      />
    </div>
  )
}
