import { useState, useCallback } from 'react'
import { Rocket, ArrowRight } from 'lucide-react'
import GitHubConnect from '../components/GitHubConnect'
import PageShell from './PageShell'

/**
 * Post-creation onboarding wizard.
 * Currently a single-step wizard for GitHub connection (skippable).
 * Can be extended with more steps later.
 */
export default function WorkspaceSetupPage({ workspaceId, workspaceName, capabilities, onComplete }) {
  const [step, setStep] = useState(0)
  const githubEnabled = capabilities?.features?.github === true

  const handleDone = useCallback(() => {
    onComplete?.()
  }, [onComplete])

  const handleSkip = useCallback(() => {
    // If no more steps, go to workspace
    handleDone()
  }, [handleDone])

  const handleConnected = useCallback(() => {
    // Auto-advance after connecting
    handleDone()
  }, [handleDone])

  // If GitHub is not enabled, skip the wizard entirely
  if (!githubEnabled) {
    // Render nothing — the parent should navigate away
    handleDone()
    return null
  }

  return (
    <PageShell title={`Set up ${workspaceName || 'Workspace'}`}>
      <div className="setup-wizard">
        <div className="setup-wizard-header">
          <Rocket size={24} />
          <h2 className="setup-wizard-title">Get started</h2>
          <p className="setup-wizard-subtitle">
            Connect your workspace to version control in one click.
          </p>
        </div>

        <div className="setup-wizard-step">
          <GitHubConnect
            workspaceId={workspaceId}
            variant="wizard"
            onConnected={handleConnected}
            onSkip={handleSkip}
            githubEnabled={githubEnabled}
          />
        </div>

        <div className="setup-wizard-footer">
          <button
            type="button"
            className="settings-btn settings-btn-primary setup-wizard-continue"
            onClick={handleDone}
          >
            Continue to workspace
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </PageShell>
  )
}
