import { describe, expect, it } from 'vitest'
import { resolveApiBaseUrl } from './baseUrl'

describe('resolveApiBaseUrl', () => {
  it('uses the Vite proxy during development even when an environment override exists', () => {
    expect(resolveApiBaseUrl('http://localhost:8000', true)).toBe('/api/v1')
  })

  it('uses the configured backend URL for production deployments', () => {
    expect(resolveApiBaseUrl('https://platform.example.com', false)).toBe(
      'https://platform.example.com/api/v1',
    )
  })

  it('uses a relative API URL when production has no configured backend', () => {
    expect(resolveApiBaseUrl(undefined, false)).toBe('/api/v1')
  })
})
