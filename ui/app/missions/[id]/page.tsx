import Link from "next/link";
import { getMission, getMissionPlans } from "@/lib/api";
import type { Plan, PlanStep, Mission } from "@/lib/types";

const STEP_COLOR: Record<string, string> = {
  succeeded: "border-emerald-700 bg-emerald-900/30",
  failed: "border-rose-800 bg-rose-900/30",
  pending: "border-zinc-700 bg-zinc-900/30",
  paused: "border-amber-700 bg-amber-900/30",
};

function stepPreview(s: PlanStep): string {
  const p = s.payload as Record<string, unknown>;
  if (s.kind === "exec") {
    const cmd = (p.cmd as string[] | undefined) ?? [];
    return cmd.join(" ").slice(0, 200);
  }
  if (s.kind === "tool") {
    return `${p.name ?? "<unnamed>"}(${JSON.stringify(p.args ?? {}).slice(0, 150)})`;
  }
  if (s.kind === "edit") {
    return (p.goal as string | undefined) ?? "<edit>";
  }
  return JSON.stringify(p).slice(0, 200);
}

export default async function MissionDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const missionId = Number(id);
  const [mission, plans]: [Mission, Plan[]] = await Promise.all([
    getMission(missionId),
    getMissionPlans(missionId),
  ]);
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <nav className="text-xs text-zinc-500 mb-4">
        <Link href="/missions" className="hover:text-zinc-300">← Missions</Link>
        <span className="mx-2">·</span>
        <Link href="/queue" className="hover:text-zinc-300">Queue</Link>
      </nav>
      <h1 className="text-2xl font-semibold">Mission #{mission.id}</h1>
      <div className="text-sm text-zinc-300 mt-1">{mission.goal}</div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <span className="px-2 py-0.5 rounded bg-zinc-800">{mission.state}</span>
        {mission.state_reason && (
          <span className="px-2 py-0.5 rounded bg-rose-900/40 text-rose-200">{mission.state_reason}</span>
        )}
        <span className="text-zinc-500">{mission.producer_key}</span>
      </div>

      <section className="mt-6 grid grid-cols-2 gap-4 text-sm">
        <div className="p-4 rounded border border-zinc-800">
          <h2 className="text-xs uppercase text-zinc-500 mb-2">Spent</h2>
          <pre className="text-xs">{JSON.stringify(mission.spent, null, 2)}</pre>
        </div>
        <div className="p-4 rounded border border-zinc-800">
          <h2 className="text-xs uppercase text-zinc-500 mb-2">Budget</h2>
          <pre className="text-xs">{JSON.stringify(mission.budget, null, 2)}</pre>
        </div>
      </section>

      {mission.needs_input_prompt && (
        <section className="mt-6 p-4 rounded border border-fuchsia-700 bg-fuchsia-950/30">
          <h2 className="text-xs uppercase text-fuchsia-200 mb-2">Needs input</h2>
          <p className="text-sm">{mission.needs_input_prompt}</p>
        </section>
      )}

      {plans.length === 0 && (
        <p className="mt-6 text-zinc-500 text-sm">No plans were emitted for this mission.</p>
      )}
      {plans.map(p => (
        <section key={p.id} className="mt-6">
          <h2 className="text-sm uppercase tracking-wide text-zinc-400 mb-3">Plan v{p.version}</h2>
          <ol className="space-y-2">
            {p.steps.map((s, i) => (
              <li key={s.step_id ?? i} className={`p-3 rounded border ${STEP_COLOR[s.status] ?? "border-zinc-800"}`}>
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono text-zinc-400">{i + 1}. {s.kind}</span>
                  <span className="text-zinc-500">{s.status} · attempt {s.attempt}</span>
                </div>
                <div className="mt-1 text-sm font-mono break-all">{stepPreview(s)}</div>
                {s.result?.error && (
                  <div className="mt-2 text-xs text-rose-300 whitespace-pre-wrap break-all">
                    {String(s.result.error).slice(0, 600)}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </section>
      ))}
    </main>
  );
}
