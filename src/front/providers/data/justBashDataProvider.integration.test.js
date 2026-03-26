import { describe, expect, it } from 'vitest'
import { createJustBashDataProvider } from './justBashDataProvider'

describe('createJustBashDataProvider integration', () => {
  it('executes core just-bash builtins against the in-memory workspace', async () => {
    const provider = createJustBashDataProvider()

    await provider.files.write('docs/notes.txt', 'alpha\nbeta\n')
    await provider.files.write('data.json', '{"name":"demo"}\n')

    await expect(provider.runCommand('ls docs')).resolves.toMatchObject({
      stdout: 'notes.txt\n',
      stderr: '',
      exitCode: 0,
    })
    await expect(provider.runCommand('cat docs/notes.txt')).resolves.toMatchObject({
      stdout: 'alpha\nbeta\n',
      stderr: '',
      exitCode: 0,
    })
    await expect(provider.runCommand('grep beta docs/notes.txt')).resolves.toMatchObject({
      stdout: 'beta\n',
      stderr: '',
      exitCode: 0,
    })
    await expect(provider.runCommand('sed -n 2p docs/notes.txt')).resolves.toMatchObject({
      stdout: 'beta\n',
      stderr: '',
      exitCode: 0,
    })
    await expect(provider.runCommand(`awk 'NR==2 { print $1 }' docs/notes.txt`)).resolves.toMatchObject({
      stdout: 'beta\n',
      stderr: '',
      exitCode: 0,
    })
    await expect(provider.runCommand('jq -r .name data.json')).resolves.toMatchObject({
      stdout: 'demo\n',
      stderr: '',
      exitCode: 0,
    })
    await expect(
      provider.runCommand('mkdir scratch && echo gamma > scratch/tmp.txt && rm scratch/tmp.txt && ls scratch'),
    ).resolves.toMatchObject({
      stdout: '',
      stderr: '',
      exitCode: 0,
    })
  })
})
