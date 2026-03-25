export default function HomePage() {
  return (
    <main className="min-h-screen bg-white text-slate-900">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="text-3xl font-semibold">Remittance Optimization MVP</h1>
        <p className="mt-3 text-slate-600">
          This is the sender/recipient/admin platform scaffold. The pricing + multi-agent
          pipeline will be integrated next.
        </p>
        <div className="mt-6 flex gap-3">
          <a
            className="rounded bg-slate-900 px-4 py-2 text-white"
            href="/sender"
          >
            Sender
          </a>
          <a
            className="rounded border border-slate-300 px-4 py-2 text-slate-900"
            href="/admin"
          >
            Admin
          </a>
        </div>
      </div>
    </main>
  );
}

