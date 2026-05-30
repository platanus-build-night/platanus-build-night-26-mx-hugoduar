import { getProducers } from "@/lib/api";
import RubricEditor from "@/components/RubricEditor";
import type { Producer } from "@/lib/types";

export default async function RubricPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const producers: Producer[] = await getProducers();
  const p = producers.find(x => x.key === key);
  if (!p) return <main className="p-8 text-zinc-100">Producer not found.</main>;
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <nav className="text-xs text-zinc-500 mb-4">
        <a href="/queue" className="hover:text-zinc-300">← Queue</a>
      </nav>
      <h1 className="text-2xl font-semibold">{p.key} · rubric (v{p.version})</h1>
      <p className="text-sm text-zinc-400 mt-1">Markdown rubric injected into the planner prompt.</p>
      <RubricEditor producerKey={p.key} initial={p.rubric_md} />
    </main>
  );
}
