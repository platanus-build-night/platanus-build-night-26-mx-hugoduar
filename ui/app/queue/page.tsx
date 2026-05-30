import { getQueue } from "@/lib/api";
import TabBar from "@/components/TabBar";
import ArtifactCard from "@/components/ArtifactCard";
import type { Artifact } from "@/lib/types";

const TABS = [
  { key: "pr", label: "Code" },
  { key: "tool", label: "Tools" },
  { key: "social_post", label: "Social" },
  { key: "analysis", label: "Clinical" },
  { key: "diagnostic", label: "Diagnostic" },
];

export default async function QueuePage({ searchParams }: { searchParams: Promise<{ kind?: string }> }) {
  const sp = await searchParams;
  const kind = sp.kind ?? "pr";
  const artifacts: Artifact[] = await getQueue(kind);
  const pending = artifacts.filter(a => a.queue_state === "pending");
  const approved = artifacts.filter(a => a.queue_state === "approved");
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Noctua · last night</h1>
        <p className="text-sm text-zinc-400">Artifacts ready for your review.</p>
      </header>
      <TabBar tabs={TABS} active={kind} />
      <section className="mt-6">
        <h2 className="text-sm uppercase tracking-wide text-zinc-400 mb-2">Pending ({pending.length})</h2>
        <div className="space-y-3">
          {pending.map(a => <ArtifactCard key={a.id} artifact={a} />)}
          {pending.length === 0 && <p className="text-zinc-500 text-sm">Nothing pending.</p>}
        </div>
      </section>
      {approved.length > 0 && (
        <section className="mt-8">
          <h2 className="text-sm uppercase tracking-wide text-zinc-400 mb-2">Recently approved ({approved.length})</h2>
          <div className="space-y-3 opacity-60">
            {approved.map(a => <ArtifactCard key={a.id} artifact={a} />)}
          </div>
        </section>
      )}
    </main>
  );
}
