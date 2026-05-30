import Link from "next/link";
import { listSandboxes } from "@/lib/api";
import type { SandboxRun, SandboxState } from "@/lib/types";

const STATE_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "All" },
  { key: "booting", label: "Booting" },
  { key: "ready", label: "Ready" },
  { key: "exited", label: "Exited" },
  { key: "torn_down", label: "Torn down" },
];

const STATE_COLOR: Record<SandboxState, string> = {
  booting: "bg-blue-700 text-blue-100",
  ready: "bg-emerald-700 text-emerald-100",
  exited: "bg-amber-700 text-amber-100",
  torn_down: "bg-zinc-700 text-zinc-200",
};

function fmt(ts?: string | null) {
  if (!ts) return "—";
  return new Date(ts).toLocaleString();
}

export default async function SandboxesPage({ searchParams }: { searchParams: Promise<{ state?: string }> }) {
  const sp = await searchParams;
  const state = sp.state ?? "";
  const sandboxes: SandboxRun[] = await listSandboxes(state || undefined);
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Sandboxes</h1>
          <p className="text-sm text-zinc-400">Every Docker container Noctua has booted for a mission.</p>
        </div>
        <div className="flex gap-3 text-sm">
          <Link href="/missions" className="text-zinc-400 hover:text-zinc-200">Missions</Link>
          <Link href="/queue" className="text-zinc-400 hover:text-zinc-200">Queue</Link>
        </div>
      </header>
      <nav className="flex gap-2 border-b border-zinc-800 mb-6">
        {STATE_FILTERS.map(f => (
          <Link key={f.key || "all"} href={f.key ? `/sandboxes?state=${f.key}` : "/sandboxes"}
            className={`px-4 py-2 text-sm rounded-t ${f.key === state ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"}`}>
            {f.label}
          </Link>
        ))}
      </nav>
      <div className="space-y-2">
        {sandboxes.length === 0 && <p className="text-zinc-500 text-sm">No sandboxes in this filter.</p>}
        {sandboxes.map(s => (
          <Link key={s.id} href={`/missions/${s.mission_id}`} className="block rounded border border-zinc-800 hover:border-zinc-600 bg-zinc-900 p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0 font-mono text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500">#{s.id}</span>
                  <span className={`px-2 py-0.5 rounded ${STATE_COLOR[s.state] ?? "bg-zinc-700"}`}>{s.state}</span>
                  <span className="text-zinc-500">mission #{s.mission_id}</span>
                </div>
                <div className="mt-1 text-zinc-300 truncate">{s.image_ref}</div>
                {s.container_id && <div className="text-zinc-500 text-[10px]">container {s.container_id.slice(0, 12)}</div>}
              </div>
              <div className="text-right text-xs text-zinc-500 shrink-0">
                <div>{fmt(s.started_at)}</div>
                {s.finished_at && <div className="mt-1">&rarr; {fmt(s.finished_at)}</div>}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
