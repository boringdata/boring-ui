/**
 * Minimal example using boring-ui components
 *
 * This demonstrates how to compose boring-ui panels
 * into a custom layout using DockLayout.
 */
import { DockLayout, FileTreePanel, EditorPanel, ShellTerminalPanel } from 'boring-ui'
import 'boring-ui/style.css'

// Define which components are available for panels
const components = {
  filetree: FileTreePanel,
  editor: EditorPanel,
  terminal: ShellTerminalPanel,
}

// Define the initial panel layout
const initialPanels = [
  {
    id: 'filetree',
    component: 'filetree',
    position: 'left',
    params: { width: 280 },
  },
  {
    id: 'editor',
    component: 'editor',
    position: 'center',
    params: {},
  },
  {
    id: 'terminal',
    component: 'terminal',
    position: 'right',
    params: { width: 400 },
  },
]

export default function App() {
  return (
    <div style={{ height: '100vh', width: '100vw' }}>
      <DockLayout
        components={components}
        panels={initialPanels}
        storageKey="minimal-layout"
      />
    </div>
  )
}
