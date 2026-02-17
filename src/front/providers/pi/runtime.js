import {
  AppStorage,
  CustomProvidersStore,
  IndexedDBStorageBackend,
  ProviderKeysStore,
  SessionsStore,
  SettingsStore,
  setAppStorage,
} from '@mariozechner/pi-web-ui'

let runtime = null

export function getPiRuntime() {
  if (runtime) return runtime

  const settings = new SettingsStore()
  const providerKeys = new ProviderKeysStore()
  const sessions = new SessionsStore()
  const customProviders = new CustomProvidersStore()

  const backend = new IndexedDBStorageBackend({
    dbName: 'boring-ui-pi-agent',
    version: 1,
    stores: [
      settings.getConfig(),
      SessionsStore.getMetadataConfig(),
      providerKeys.getConfig(),
      customProviders.getConfig(),
      sessions.getConfig(),
    ],
  })

  settings.setBackend(backend)
  providerKeys.setBackend(backend)
  sessions.setBackend(backend)
  customProviders.setBackend(backend)

  const storage = new AppStorage(settings, providerKeys, sessions, customProviders, backend)
  setAppStorage(storage)

  runtime = {
    storage,
    settings,
    providerKeys,
    sessions,
    customProviders,
  }

  return runtime
}
