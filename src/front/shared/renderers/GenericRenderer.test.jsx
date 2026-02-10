/**
 * Tests for shared GenericRenderer component.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import GenericRenderer from './GenericRenderer'

describe('GenericRenderer', () => {
  it('renders tool name', () => {
    render(<GenericRenderer toolName="WebSearch" />)
    expect(screen.getByText('WebSearch')).toBeTruthy()
  })

  it('defaults tool name to "Tool"', () => {
    render(<GenericRenderer />)
    expect(screen.getByText('Tool')).toBeTruthy()
  })

  it('shows description', () => {
    render(<GenericRenderer toolName="Custom" description="doing stuff" />)
    expect(screen.getByText('doing stuff')).toBeTruthy()
  })

  it('shows output content', () => {
    render(<GenericRenderer toolName="Tool" output="some output" />)
    expect(screen.getByText('some output')).toBeTruthy()
  })

  it('shows error message', () => {
    render(<GenericRenderer toolName="Tool" error="Something failed" />)
    expect(screen.getByText('Something failed')).toBeTruthy()
  })

  it('shows running state', () => {
    render(<GenericRenderer toolName="Tool" status="running" />)
    expect(screen.getByText(/Running/)).toBeTruthy()
  })

  it('extracts from NormalizedToolResult', () => {
    const result = {
      toolType: 'generic',
      toolName: 'WebFetch',
      status: 'complete',
      description: 'Fetching URL',
      output: { content: 'page content' },
    }
    render(<GenericRenderer result={result} />)
    expect(screen.getByText('WebFetch')).toBeTruthy()
    expect(screen.getByText('Fetching URL')).toBeTruthy()
    expect(screen.getByText('page content')).toBeTruthy()
  })
})
