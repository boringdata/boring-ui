/**
 * Tests for shared DiffView component.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import DiffView, { SimpleDiff } from './DiffView'

describe('DiffView', () => {
  it('renders null when diff is null', () => {
    const { container } = render(<DiffView diff={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders null when diff is empty string', () => {
    const { container } = render(<DiffView diff="" />)
    expect(container.innerHTML).toBe('')
  })

  it('renders null when diff is empty array', () => {
    const { container } = render(<DiffView diff={[]} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders additions with green styling', () => {
    const { container } = render(<DiffView diff="+added line" />)
    const line = container.querySelector('.shared-diff-view > div')
    expect(line.style.backgroundColor).toContain('diff-add-bg')
    expect(line.textContent).toContain('+added line')
  })

  it('renders deletions with red styling', () => {
    const { container } = render(<DiffView diff="-removed line" />)
    const line = container.querySelector('.shared-diff-view > div')
    expect(line.style.backgroundColor).toContain('diff-remove-bg')
    expect(line.textContent).toContain('-removed line')
  })

  it('renders context lines with transparent background', () => {
    const { container } = render(<DiffView diff=" context line" />)
    const line = container.querySelector('.shared-diff-view > div')
    expect(line.style.backgroundColor).toBe('transparent')
  })

  it('renders header lines with muted text', () => {
    const { container } = render(<DiffView diff="@@ -1,3 +1,4 @@" />)
    const line = container.querySelector('.shared-diff-view > div')
    expect(line.style.color).toContain('muted')
  })

  it('does not classify +++ as addition', () => {
    const { container } = render(<DiffView diff="+++ b/file.js" />)
    const line = container.querySelector('.shared-diff-view > div')
    // Should be header, not add — no green bg
    expect(line.style.backgroundColor).toBe('transparent')
  })

  it('accepts string array input', () => {
    const lines = ['+added', '-removed', ' context']
    const { container } = render(<DiffView diff={lines} />)
    const lineEls = container.querySelectorAll('.shared-diff-view > div')
    expect(lineEls).toHaveLength(3)
  })

  it('accepts parsed DiffLine array input', () => {
    const lines = [
      { content: '+added', type: 'add' },
      { content: '-removed', type: 'remove' },
    ]
    const { container } = render(<DiffView diff={lines} />)
    const lineEls = container.querySelectorAll('.shared-diff-view > div')
    expect(lineEls).toHaveLength(2)
  })

  it('renders multi-line diff correctly', () => {
    const diff = '@@ -1,2 +1,3 @@\n context\n-old\n+new\n+extra'
    const { container } = render(<DiffView diff={diff} />)
    const lineEls = container.querySelectorAll('.shared-diff-view > div')
    expect(lineEls).toHaveLength(5)
  })

  it('applies maxHeight when provided', () => {
    const { container } = render(<DiffView diff="+line" maxHeight={200} />)
    const wrapper = container.querySelector('.shared-diff-view')
    expect(wrapper.style.maxHeight).toBe('200px')
    expect(wrapper.style.overflow).toBe('auto')
  })

  it('does not set maxHeight by default', () => {
    const { container } = render(<DiffView diff="+line" />)
    const wrapper = container.querySelector('.shared-diff-view')
    expect(wrapper.style.maxHeight).toBe('')
  })

  it('shows line numbers when showLineNumbers is true', () => {
    const lines = [
      { content: '+line1', type: 'add' },
      { content: '+line2', type: 'add' },
    ]
    const { container } = render(<DiffView diff={lines} showLineNumbers />)
    const lineEls = container.querySelectorAll('.shared-diff-view > div')
    expect(lineEls).toHaveLength(2)
    expect(lineEls[0].textContent).toContain('1')
    expect(lineEls[1].textContent).toContain('2')
  })

  it('hides line numbers by default', () => {
    const { container } = render(<DiffView diff="+line" />)
    const line = container.querySelector('.shared-diff-view > div')
    // Should only have the content span, not a line number span
    const spans = line.querySelectorAll('span')
    expect(spans).toHaveLength(1) // Just the content span
  })

  it('applies custom className', () => {
    const { container } = render(<DiffView diff="+line" className="my-diff" />)
    const wrapper = container.querySelector('.shared-diff-view')
    expect(wrapper.classList.contains('my-diff')).toBe(true)
  })

  it('renders empty line as space character', () => {
    const lines = [{ content: '', type: 'context' }]
    const { container } = render(<DiffView diff={lines} />)
    const contentSpan = container.querySelector('.shared-diff-view > div > span')
    // Empty content should render as a non-breaking space
    expect(contentSpan.textContent).toBe(' ')
  })
})

describe('SimpleDiff', () => {
  it('renders null when both old and new are empty strings', () => {
    // Empty strings "" split to [""] creating 1-char diff lines "-" and "+"
    // which get parsed as remove/add types, so DiffView still renders
    // This is expected behavior — SimpleDiff guards null/undefined, not empty strings
    const { container } = render(<SimpleDiff oldContent="" newContent="" />)
    // parseDiffLines(["-", "+"]) → 2 DiffLine objects → DiffView renders
    const wrapper = container.querySelector('.shared-diff-view')
    // Actually the guard `if (!oldContent && !newContent)` catches empty strings
    expect(wrapper).toBeNull()
  })

  it('renders null when both are null/undefined', () => {
    const { container } = render(<SimpleDiff oldContent={null} newContent={null} />)
    expect(container.innerHTML).toBe('')
  })

  it('shows old content as removals', () => {
    const { container } = render(<SimpleDiff oldContent="old line" newContent="" />)
    const lines = container.querySelectorAll('.shared-diff-view > div')
    const removeLines = Array.from(lines).filter(
      (el) => el.style.backgroundColor.includes('remove')
    )
    expect(removeLines.length).toBeGreaterThan(0)
    expect(removeLines[0].textContent).toContain('-old line')
  })

  it('shows new content as additions', () => {
    const { container } = render(<SimpleDiff oldContent="" newContent="new line" />)
    const lines = container.querySelectorAll('.shared-diff-view > div')
    const addLines = Array.from(lines).filter(
      (el) => el.style.backgroundColor.includes('add')
    )
    expect(addLines.length).toBeGreaterThan(0)
    expect(addLines[0].textContent).toContain('+new line')
  })

  it('shows both removals and additions', () => {
    const { container } = render(
      <SimpleDiff oldContent="old" newContent="new" />,
    )
    const lines = container.querySelectorAll('.shared-diff-view > div')
    expect(lines.length).toBe(2)
  })
})
