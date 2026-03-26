/**
 * Capabilities service — transport-independent capability discovery.
 * Mirrors Python's capabilities.py build_capabilities_response().
  *
 * @deprecated Interface only — factory removed. Routes import *Impl directly.
 */
import type { CapabilitiesResponse, RouterInfo } from '../../shared/types.js'
import type { ServerConfig } from '../config.js'

export interface CapabilitiesServiceDeps {
  config: ServerConfig
  enabledRouters: RouterInfo[]
  enabledFeatures: Record<string, boolean>
}

export interface CapabilitiesService {
  getCapabilities(): CapabilitiesResponse
}

