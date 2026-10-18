import { useQuery } from '@tanstack/react-query'

export function App() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? '/api/v1'}/health/ready`)
      if (!response.ok) throw new Error('The API or database is unavailable.')
      const result: { status: string } = await response.json()
      return result
    },
    retry: 1,
  })

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <p className="text-sm font-semibold uppercase tracking-widest text-teal-700">SubTrack</p>
      <h1 className="mt-4 text-3xl font-semibold">Subscription & recurring payment manager</h1>
      <p className="mt-6">Demo and educational use with uploaded or simulated data.</p>
      <section className="mt-8 rounded-xl border border-slate-300 p-6" aria-label="Service status">
        <h2 className="text-xl font-semibold">Scaffold readiness</h2>
        <p className="mt-3" role="status">
          {health.isPending ? 'Checking services…' : health.isError
            ? 'Services unavailable. Start the API and database, then retry.'
            : `API and database: ${health.data.status}`}
        </p>
        {health.isError ? (
          <button className="mt-4 rounded bg-teal-700 px-4 py-2 text-white"
            onClick={() => void health.refetch()}>Retry connection</button>
        ) : null}
      </section>
      <p className="mt-6 text-sm text-slate-600">
        Service scaffold. The detection core is tested; authentication, uploads, and spending views
        are not implemented yet.
      </p>
    </main>
  )
}

