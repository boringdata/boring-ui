/**
 * Dynamic workspace panel loader.
 *
 * Loads React components from workspace plugin directories via the
 * @workspace Vite alias which points to {WORKSPACE_ROOT}/kurt/panels/.
 *
 * @module workspace/loader
 */

/**
 * Dynamically import workspace panel components.
 *
 * @param {Array<{id: string, name: string, path: string}>} workspacePanes
 *   Panel descriptors from /api/capabilities → workspace_panes
 * @returns {Promise<Object<string, React.ComponentType>>}
 *   Map of pane id → default-exported React component
 */
export async function loadWorkspacePanes(workspacePanes) {
  const loaded = {}

  for (const pane of workspacePanes) {
    try {
      // @vite-ignore tells Vite not to try to statically analyse this import
      const mod = await import(/* @vite-ignore */ `@workspace/${pane.path}`)
      loaded[pane.id] = mod.default
    } catch (err) {
      console.warn(`[Workspace] Failed to load panel ${pane.id}:`, err)
    }
  }

  return loaded
}
