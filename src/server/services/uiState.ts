/**
 * UI State service — persists frontend UI state on the server.
 * Mirrors Python's modules/ui_state/router.py.
  *
 * @deprecated Interface only — factory removed. Routes import *Impl directly.
 */

export interface UIStateService {
  get(key: string): Promise<unknown | null>
  set(key: string, value: unknown): Promise<void>
  delete(key: string): Promise<boolean>
  list(): Promise<string[]>
}

