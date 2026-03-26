/**
 * Exec service — transport-independent business logic for command execution.
 * The BwrapBackend provides sandboxed execution via bubblewrap.
  *
 * @deprecated Interface only — factory removed. Routes import *Impl directly.
 */

export interface ExecResult {
  stdout: string
  stderr: string
  exit_code: number
}

export interface ExecServiceDeps {
  workspaceRoot: string
  bwrapEnabled: boolean
}

export interface ExecService {
  exec(command: string, cwd?: string): Promise<ExecResult>
  pythonExec(code: string, cwd?: string): Promise<ExecResult>
}

