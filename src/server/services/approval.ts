/**
 * Approval service — transport-independent tool approval workflow.
 * Mirrors Python's approval.py ApprovalStore.
  *
 * @deprecated Interface only — factory removed. Routes import *Impl directly.
 */
import type { ApprovalRequest } from '../../shared/types.js'

export interface ApprovalStore {
  create(
    requestId: string,
    data: Omit<ApprovalRequest, 'id' | 'status' | 'created_at'>,
  ): Promise<void>
  get(requestId: string): Promise<ApprovalRequest | null>
  update(
    requestId: string,
    decision: 'approve' | 'deny',
    reason?: string,
  ): Promise<void>
  listPending(): Promise<ApprovalRequest[]>
  delete(requestId: string): Promise<boolean>
}

