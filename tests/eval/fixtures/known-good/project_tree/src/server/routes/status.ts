export function registerStatusRoutes(app) {
  app.get('/health', async () => ({
    ok: true,
    app: 'ce-0324-goodgood',
    eval_id: 'child-eval-20260324T120000Z-goodgood',
    verification_nonce: 'fixture-known-good',
    custom: true,
  }))

  app.get('/info', async () => ({
    name: 'ce-0324-goodgood',
    version: '0.1.0',
    eval_id: 'child-eval-20260324T120000Z-goodgood',
  }))
}
