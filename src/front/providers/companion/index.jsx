// Stub adapter for now — renders placeholder
function CompanionStub({ onToggleCollapse }) {
  return (
    <>
      <div className="terminal-header">
        <span className="terminal-title-text">Companion</span>
        <div className="terminal-header-spacer" />
      </div>
      <div className="terminal-body">
        <div className="terminal-instance active" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#888' }}>
          Companion provider loaded
        </div>
      </div>
    </>
  )
}

export const config = {
  id: 'companion',
  label: 'Companion',
  component: CompanionStub,
  requiresCapabilities: ['companion'],
}

export default config
