import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { App } from './App'

afterEach(() => vi.unstubAllGlobals())

test('renders readiness returned by the API and the educational notice', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ready' }) }))
  render(<QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider>)
  expect(await screen.findByText('API and database: ready')).toBeInTheDocument()
  expect(screen.getByText(/Demo and educational use/)).toBeInTheDocument()
})

test('shows recovery action when the API fails', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
  const client = new QueryClient({ defaultOptions: { queries: { retryDelay: 0 } } })
  render(<QueryClientProvider client={client}><App /></QueryClientProvider>)
  expect(await screen.findByRole('button', { name: 'Retry connection' })).toBeInTheDocument()
})

