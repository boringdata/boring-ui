import { useCallback } from 'react'
import { useArtifactController } from './useArtifactController'
import {
  bridgeToolResultToArtifact,
  bridgeOpenPanelToArtifact,
  bridgeArtifactCardToArtifact,
} from '../utils/toolArtifactBridge'

/**
 * useArtifactRouting — Unified routing layer for all artifact open actions.
 *
 * Ensures that tool results, open_panel calls, ArtifactCard clicks, and
 * explicit file-open requests all converge on the same artifact controller.
 * This prevents duplicate panels and ensures consistent dedup behavior.
 *
 * Returns stable callbacks for each entry point:
 *   - handleToolResult(toolName, args, result)  — called after a tool completes
 *   - handleOpenPanel(payload)                  — called by open_panel tool
 *   - handleArtifactCardOpen(cardData)          — called when user clicks a card
 *   - handleOpenFile(path)                      — called by open_file tool or browse
 *
 * All callbacks create a SurfaceArtifact and pass it to the artifact controller's
 * `open()`, which handles deduplication by canonicalKey.
 *
 * @param {string} activeSessionId - Current session ID for provenance
 * @param {string} [activeMessageId] - Current message ID for provenance (optional)
 */
export function useArtifactRouting(activeSessionId, activeMessageId) {
  const { open: openArtifact, focus, artifacts, orderedIds } = useArtifactController()

  /**
   * Route a tool result to the Surface if it produces an artifact.
   */
  const handleToolResult = useCallback((toolName, args, result) => {
    const { shouldOpen, artifact } = bridgeToolResultToArtifact(
      toolName,
      args,
      result,
      activeSessionId,
      activeMessageId,
    )

    if (shouldOpen && artifact) {
      openArtifact(artifact)
    }

    return { shouldOpen, artifact }
  }, [activeSessionId, activeMessageId, openArtifact])

  /**
   * Route an open_panel tool call to the Surface.
   */
  const handleOpenPanel = useCallback((payload) => {
    const { shouldOpen, artifact } = bridgeOpenPanelToArtifact(
      payload,
      activeSessionId,
      activeMessageId,
    )

    if (shouldOpen && artifact) {
      openArtifact(artifact)
    }

    return { shouldOpen, artifact }
  }, [activeSessionId, activeMessageId, openArtifact])

  /**
   * Route an ArtifactCard click to the Surface.
   * The card data may already have a canonicalKey for dedup.
   */
  const handleArtifactCardOpen = useCallback((cardData) => {
    const artifact = bridgeArtifactCardToArtifact(
      cardData,
      activeSessionId,
      activeMessageId,
    )

    if (artifact) {
      openArtifact(artifact)
    }

    return artifact
  }, [activeSessionId, activeMessageId, openArtifact])

  /**
   * Route a file-open request (from browse, tree click, or tool) to the Surface.
   */
  const handleOpenFile = useCallback((path) => {
    if (!path || typeof path !== 'string') return null
    const trimmedPath = path.trim()
    if (!trimmedPath) return null

    const { shouldOpen, artifact } = bridgeToolResultToArtifact(
      'open_file',
      { path: trimmedPath },
      {},
      activeSessionId,
      activeMessageId,
    )

    if (shouldOpen && artifact) {
      openArtifact(artifact)
    }

    return artifact
  }, [activeSessionId, activeMessageId, openArtifact])

  return {
    handleToolResult,
    handleOpenPanel,
    handleArtifactCardOpen,
    handleOpenFile,
    // Expose controller state for convenience
    artifacts,
    orderedIds,
    focusArtifact: focus,
  }
}
