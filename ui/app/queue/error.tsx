"use client";

export default function QueueError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <h1 className="text-2xl font-semibold">Queue failed to load</h1>
      <p className="text-sm text-zinc-400 mt-2">
        Usually this means the UI bearer token doesn&apos;t match the API. Restart{" "}
        <code className="text-zinc-200">npm run dev</code> after editing{" "}
        <code className="text-zinc-200">ui/.env.local</code>, and confirm{" "}
        <code className="text-zinc-200">NEXT_PUBLIC_NOCTUA_TOKEN</code> matches{" "}
        <code className="text-zinc-200">NOCTUA_API_TOKEN</code> in the project root{" "}
        <code className="text-zinc-200">.env</code>.
      </p>
      <pre className="mt-4 p-4 rounded border border-zinc-800 bg-zinc-900 text-xs overflow-x-auto whitespace-pre-wrap">
        {error.message}
      </pre>
      <button
        onClick={reset}
        className="mt-4 px-4 py-2 rounded bg-zinc-800 hover:bg-zinc-700 text-sm"
      >
        Retry
      </button>
    </main>
  );
}
