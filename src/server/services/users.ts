/**
 * Users service — transport-independent user identity + settings.
 * Mirrors Python's me_router_neon.py.
  *
 * @deprecated Interface only — factory removed. Routes import *Impl directly.
 */
import type { User } from '../../shared/types.js'

export interface UserServiceDeps {
  databaseUrl?: string
}

export interface UserService {
  getById(userId: string): Promise<User | null>
  getByEmail(email: string): Promise<User | null>
  upsert(userId: string, data: { email: string; name?: string }): Promise<User>
  getSettings(userId: string): Promise<Record<string, unknown>>
  putSettings(
    userId: string,
    settings: Record<string, unknown>,
  ): Promise<void>
}

