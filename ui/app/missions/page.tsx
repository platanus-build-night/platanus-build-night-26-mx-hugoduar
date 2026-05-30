import Link from "next/link";
import { listMissions } from "@/lib/api";
import type { MissionListItem, MissionState } from "@/lib/types";

const STATE_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "All" },
  { key: "running", label: "Running" },
  { key: "queued", label: "Queued" },
  { key: "needs_input", label: "Needs input" },
  { key: "succeeded", label: "Succeeded" },
  { key: "failed", label: "Failed" },
  { key: "stopped", label: "Stopped" },
];

const STATE_COLOR: Record<MissionState, string> = {
  queued: "bg-zinc-700 text-zinc-200",
  running: "bg-blue-700 text-blue-100",
  succeeded: "bg-emerald-700 text-emerald-100",
  failed: "bg-rose-800 text-rose-100",
  stopped: "bg-amber-700 text-amber-100",
  needs_input: "bg-fuchsia-700 text-fuchsia-100",
};

function fmt(ts?: string | null) {
  if (!ts) return "—";
  return new Date(ts).toLocaleString();
}

export default async function MissionsPage({ searchParams }: { searchParams: Promise<{ state?: string }> }) {
  const sp = await searchParams;
  const state = sp.state ?? "";
  const missions: MissionListItem[] = await listMissions(state || undefined);
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Missions</h1>
          <p className="text-sm text-zinc-400">Everything Noctua has tried, not just the ones with artifacts.</p>
        </div>
        <Link href="/queue" className="text-sm text-zinc-400 hover:text-zinc-200">Queue →</Link>
      </header>
      <nav className="flex gap-2 border-b border-zinc-800 mb-6">
        {STATE_FILTERS.map(f => (
          <Link key={f.key || "all"} href={f.key ? `/missions?state=${f.key}` : "/missions"}
            className={`px-4 py-2 text-sm rounded-t ${f.key === state ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"}`}>
            {f.label}
          </Link>
        ))}
      </nav>
      <div className="space-y-2">
        {missions.length === 0 && <p className="text-zinc-500 text-sm">No missions in this filter.</p>}
        {missions.map(m => (
          <Link key={m.id} href={`/missions/${m.id}`}
            className="block rounded border border-zinc-800 hover:border-zinc-600 bg-zinc-900 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-zinc-500">#{m.id}</span>
                  <span className={`px-2 py-0.5 rounded ${STATE_COLOR[m.state] ?? "bg-zinc-700"}`}>{m.state}</span>
                  <span className="text-zinc-500">{m.producer_key}</span>
                </div>
                <div className="font-medium mt-1 truncate">{m.goal}</div>
                {m.state_reason && <div className="text-xs text-rose-300 mt-1">{m.state_reason}</div>}
              </div>
              <div className="text-right text-xs text-zinc-500 shrink-0">
                <div>{fmt(m.finished_at ?? m.created_at)}</div>
                <div className="mt-1 font-mono">
                  {(m.spent?.tokens ?? 0)} tok · {(m.spent?.tool_calls ?? 0)} tools
                </div>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
