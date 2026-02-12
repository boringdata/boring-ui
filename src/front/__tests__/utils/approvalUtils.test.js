import { describe, it, expect } from 'vitest'
import {
  extractFilename,
  normalizeApprovalPath,
  getReviewTitle,
} from '../../utils/approvalUtils'

describe('extractFilename', () => {
  it('extracts filename from path', () => {
    expect(extractFilename('src/components/App.jsx')).toBe('App.jsx')
  })

  it('handles single filename (no slashes)', () => {
    expect(extractFilename('README.md')).toBe('README.md')
  })

  it('handles deeply nested path', () => {
    expect(extractFilename('a/b/c/d/file.txt')).toBe('file.txt')
  })

  it('returns empty string for empty input', () => {
    expect(extractFilename('')).toBe('')
  })

  it('returns empty string for null/undefined', () => {
    expect(extractFilename(null)).toBe('')
    expect(extractFilename(undefined)).toBe('')
  })
})

describe('normalizeApprovalPath', () => {
  it('returns project_path when available', () => {
    const approval = { project_path: 'src/a.js', file_path: '/abs/src/a.js' }
    expect(normalizeApprovalPath(approval, '/abs')).toBe('src/a.js')
  })

  it('strips projectRoot from file_path', () => {
    const approval = { file_path: '/home/user/project/src/App.jsx' }
    expect(normalizeApprovalPath(approval, '/home/user/project')).toBe('src/App.jsx')
  })

  it('strips projectRoot with trailing slash', () => {
    const approval = { file_path: '/project/src/a.js' }
    expect(normalizeApprovalPath(approval, '/project/')).toBe('src/a.js')
  })

  it('returns file_path as-is when no projectRoot match', () => {
    const approval = { file_path: '/other/path/file.js' }
    expect(normalizeApprovalPath(approval, '/project')).toBe('/other/path/file.js')
  })

  it('returns file_path when projectRoot is null', () => {
    const approval = { file_path: '/abs/path/file.js' }
    expect(normalizeApprovalPath(approval, null)).toBe('/abs/path/file.js')
  })

  it('returns empty string when approval is null', () => {
    expect(normalizeApprovalPath(null, '/project')).toBe('')
  })

  it('returns empty string when approval has no path fields', () => {
    expect(normalizeApprovalPath({}, '/project')).toBe('')
  })

  it('returns empty string when file_path is empty', () => {
    expect(normalizeApprovalPath({ file_path: '' }, '/project')).toBe('')
  })
})

describe('getReviewTitle', () => {
  it('uses filename from normalized path', () => {
    const approval = { file_path: '/project/src/App.jsx', tool_name: 'Edit' }
    expect(getReviewTitle(approval, '/project')).toBe('Review: App.jsx')
  })

  it('uses project_path over file_path', () => {
    const approval = { project_path: 'src/config.json', tool_name: 'Write' }
    expect(getReviewTitle(approval, '/project')).toBe('Review: config.json')
  })

  it('falls back to tool_name when no path', () => {
    const approval = { tool_name: 'Bash' }
    expect(getReviewTitle(approval, '/project')).toBe('Review: Bash')
  })

  it('returns "Review" when no path and no tool_name', () => {
    expect(getReviewTitle({}, '/project')).toBe('Review')
  })

  it('returns "Review" for null approval', () => {
    expect(getReviewTitle(null, '/project')).toBe('Review')
  })

  it('handles approval with only file_path and no projectRoot', () => {
    const approval = { file_path: '/abs/path/file.js' }
    expect(getReviewTitle(approval, null)).toBe('Review: file.js')
  })
})
