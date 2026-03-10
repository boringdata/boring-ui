import { Check, GitBranch, Cloud } from 'lucide-react'
import { useGitStatus, useGitBranch } from '../providers/data'
import Tooltip from './Tooltip'

/**
 * Sync status footer for the file tree sidebar.
 *
 * Shows: [branch indicator] [sync state icon + label]
 *
 * Note: useGitStatus is shared via React Query's cache deduplication —
 * FileTreePanel's existing 5s poll populates the same query key, so this
 * component reads from cache without triggering duplicate requests.
 * Branch is polled at 30s since it only changes on explicit user action.
 */
export default function SyncStatusFooter() {
  const { data: gitData } = useGitStatus()
  const { data: branch } = useGitBranch({ refetchInterval: 30000 })
  const isRepo = gitData?.is_repo
  const files = gitData?.files || []
  const dirtyCount = files.filter((f) => f.status && f.status !== 'C').length

  if (!isRepo) return null

  const isClean = dirtyCount === 0
  const branchLabel = branch || null
  const isMain = branch === 'main' || branch === 'master'

  return (
    <div className="sync-status-footer">
      {branchLabel && (
        <Tooltip label={`Branch: ${branchLabel}`}>
          <span className={`sync-branch ${isMain ? '' : 'sync-branch--draft'}`}>
            <GitBranch size={12} />
            <span className="sync-branch-name">{branchLabel}</span>
          </span>
        </Tooltip>
      )}
      <span className="sync-state-spacer" />
      <Tooltip label={isClean ? 'All changes saved' : `${dirtyCount} unsaved change(s)`}>
        <span className={`sync-state ${isClean ? 'sync-state--ok' : 'sync-state--dirty'}`}>
          {isClean ? (
            <>
              <Check size={12} />
              <span>Saved</span>
            </>
          ) : (
            <>
              <Cloud size={12} />
              <span>{dirtyCount} change{dirtyCount !== 1 ? 's' : ''}</span>
            </>
          )}
        </span>
      </Tooltip>
    </div>
  )
}
