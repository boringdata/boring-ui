# bd-1wi2.2.1: Copy vendored upstream Companion app

*2026-02-14T20:42:37Z by Showboat 0.5.0*

```bash
npm run test:run
```

```output

> boring-ui@0.1.0 test:run
> vitest run


 RUN  v1.6.1 /home/ubuntu/projects/boring-ui


⎯⎯⎯⎯⎯⎯ Unhandled Errors ⎯⎯⎯⎯⎯⎯

Vitest caught 20 unhandled errors during the test run.
This might cause false positive tests. Resolve unhandled errors to make sure your tests are not affected.

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }

⎯⎯⎯⎯⎯⎯ Unhandled Error ⎯⎯⎯⎯⎯⎯⎯
TypeError: port.addListener is not a function. (In 'port.addListener("message", fn)', 'port.addListener' is undefined)
 ❯ on node_modules/vitest/dist/vendor/utils.0uYuCbzo.js:13:12
 ❯ createBirpc node_modules/vitest/dist/vendor/index.8bPxjt7g.js:55:14
 ❯ createRuntimeRpc node_modules/vitest/dist/vendor/rpc.joBhAkyK.js:48:30
 ❯ run node_modules/vitest/dist/worker.js:77:31
 ❯ <anonymous> node_modules/tinypool/dist/esm/entry/worker.js:72:26
 ❯ processTicksAndRejections native:7:39

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯
Serialized Error: { line: 13, column: 12, sourceURL: '/home/ubuntu/projects/boring-ui/node_modules/vitest/dist/vendor/utils.0uYuCbzo.js' }
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

 Test Files  no tests
      Tests  no tests
     Errors  20 errors
   Start at  20:42:41
   Duration  1.05s (transform 0ms, setup 0ms, collect 0ms, tests 0ms, environment 0ms, prepare 0ms)

```
