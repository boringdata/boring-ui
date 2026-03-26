import { useEffect, useMemo, useRef } from 'react'
import {
  createQueryClient,
  getDataProvider,
  getDataProviderFactory,
  createHttpProvider,
  createJustBashDataProvider,
  createLightningDataProvider,
} from '../providers/data'
import {
  buildLightningFsNamespace,
  resolveLightningFsUserScope,
  resolveLightningFsWorkspaceScope,
} from '../providers/data/lightningFsNamespace'
import { getFrontendStateClientId } from '../utils/frontendState'
import { getCachedScopedValue, isStableLightningUserScope } from '../utils/panelConfig'

export default function useDataProviderScope({
  config,
  storagePrefix,
  currentWorkspaceId,
  menuUserId,
  menuUserEmail,
  userMenuAuthStatus,
}) {
  const dataProviderCacheRef = useRef(new Map())
  const queryClientCacheRef = useRef(new Map())

  const configuredDataBackend = String(config?.data?.backend || 'http')
    .trim()
    .toLowerCase()
  const lightningFsSessionScope = useMemo(
    () => getFrontendStateClientId(storagePrefix),
    [storagePrefix],
  )
  const configuredLightningFsBaseName = String(
    config?.data?.lightningfs?.name || 'boring-fs',
  ).trim()
  const lightningFsUserScope = useMemo(
    () => resolveLightningFsUserScope({
      userId: menuUserId,
      userEmail: menuUserEmail,
      authStatus: userMenuAuthStatus,
      sessionScope: lightningFsSessionScope,
    }),
    [menuUserId, menuUserEmail, userMenuAuthStatus, lightningFsSessionScope],
  )
  const lightningFsWorkspaceScope = useMemo(
    () => resolveLightningFsWorkspaceScope(currentWorkspaceId),
    [currentWorkspaceId],
  )
  const resolvedLightningFsName = useMemo(
    () => buildLightningFsNamespace({
      baseName: configuredLightningFsBaseName,
      origin: typeof window !== 'undefined' ? window.location.origin : 'local',
      userScope: lightningFsUserScope,
      workspaceScope: lightningFsWorkspaceScope,
    }),
    [
      configuredLightningFsBaseName,
      lightningFsUserScope,
      lightningFsWorkspaceScope,
    ],
  )
  const strictDataBackend = Boolean(config?.data?.strictBackend)
  const lightningFsProviderCacheKey = `user:${lightningFsUserScope}|fs:${resolvedLightningFsName}`
  const justBashProviderCacheKey = `user:${lightningFsUserScope}|workspace:${lightningFsWorkspaceScope}|session:${lightningFsSessionScope}`
  const isLightningBackend = (
    configuredDataBackend === 'lightningfs' || configuredDataBackend === 'lightning-fs'
  )
  const isJustBashBackend = configuredDataBackend === 'justbash'
  const dataProviderScopeKey = (
    isLightningBackend
      ? `lightningfs:${lightningFsProviderCacheKey}`
      : isJustBashBackend
        ? `justbash:${justBashProviderCacheKey}`
      : `backend:${configuredDataBackend || 'http'}`
  )
  const queryClient = useMemo(
    () => getCachedScopedValue(
      queryClientCacheRef.current,
      dataProviderScopeKey,
      () => createQueryClient(),
      (client) => client?.clear?.(),
    ),
    [dataProviderScopeKey],
  )
  const dataProvider = useMemo(
    () => {
      const injected = getDataProvider()
      if (injected) return injected

      if (!configuredDataBackend || configuredDataBackend === 'http') {
        return createHttpProvider({ workspaceId: currentWorkspaceId })
      }

      if (isLightningBackend) {
        return getCachedScopedValue(
          dataProviderCacheRef.current,
          lightningFsProviderCacheKey,
          () => createLightningDataProvider({ fsName: resolvedLightningFsName }),
        )
      }

      if (isJustBashBackend) {
        return getCachedScopedValue(
          dataProviderCacheRef.current,
          justBashProviderCacheKey,
          () => createJustBashDataProvider(),
        )
      }

      const factory = getDataProviderFactory(configuredDataBackend)
      if (factory) return factory()

      if (strictDataBackend) {
        throw new Error(
          `[DataProvider] Unknown configured backend "${configuredDataBackend}" (strict mode enabled)`,
        )
      }

      console.warn(
        `[DataProvider] Unknown configured backend "${configuredDataBackend}", falling back to http`,
      )
      return createHttpProvider({ workspaceId: currentWorkspaceId })
    },
    [
      configuredDataBackend,
      currentWorkspaceId,
      isJustBashBackend,
      isLightningBackend,
      justBashProviderCacheKey,
      lightningFsProviderCacheKey,
      resolvedLightningFsName,
      strictDataBackend,
    ],
  )

  useEffect(() => {
    if (!isLightningBackend && !isJustBashBackend) return
    if (!isStableLightningUserScope(lightningFsUserScope)) return

    const providerKeyPrefix = `user:${lightningFsUserScope}|`
    const queryKeyPrefix = isLightningBackend
      ? `lightningfs:${providerKeyPrefix}`
      : `justbash:${providerKeyPrefix}`
    const queryKeyStartsWith = isLightningBackend ? 'lightningfs:' : 'justbash:'

    Array.from(dataProviderCacheRef.current.keys()).forEach((key) => {
      if (key.startsWith(providerKeyPrefix)) return
      dataProviderCacheRef.current.delete(key)
    })

    Array.from(queryClientCacheRef.current.entries()).forEach(([key, client]) => {
      if (!key.startsWith(queryKeyStartsWith)) return
      if (key.startsWith(queryKeyPrefix)) return
      client?.clear?.()
      queryClientCacheRef.current.delete(key)
    })
  }, [isJustBashBackend, isLightningBackend, lightningFsUserScope])

  return {
    configuredDataBackend,
    dataProviderScopeKey,
    queryClient,
    dataProvider,
  }
}
