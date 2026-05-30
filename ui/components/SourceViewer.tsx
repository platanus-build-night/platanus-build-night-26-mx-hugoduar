export default function SourceViewer({ artifactId }: { artifactId: number }) {
  return (
    <section className="mt-6 p-4 rounded border border-zinc-800 bg-zinc-900">
      <h2 className="text-sm uppercase tracking-wide text-zinc-400 mb-2">Tool source (artifact #{artifactId})</h2>
      <p className="text-xs text-zinc-500">Source viewer to be wired to a `/api/artifacts/:id/source` endpoint (v0.2). For now, approve to graduate.</p>
    </section>
  );
}
