import Link from "next/link";
import { listSandboxes } from "@/lib/api";
import type { SandboxRun } from "@/lib/types";
import SiteHeader from "@/components/SiteHeader";
import SandboxCard from "@/components/SandboxCard";
import { StatsDisplay } from "@/components/tool-ui/stats-display";
import type { StatItem } from "@/components/tool-ui/stats-display";

const STATE_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "All" },
  { key: "booting", label: "Booting" },
  { key: "ready", label: "Ready" },
  { key: "exited", label: "Exited" },
  { key: "torn_down", label: "Torn down" },
];

function fleetStats(sandboxes: SandboxRun[]): StatItem[] {
  const counts: Record<string, number> = {};
  let live = 0;
  for (const s of sandboxes) {
    counts[s.state] = (counts[s.state] ?? 0) + 1;
    if (s.state === "booting" || s.state === "ready") live += 1;
  }
  return [
    { key: "total", label: "Total", value: sandboxes.length, format: { kind: "number" } },
    { key: "live", label: "Live", value: live, format: { kind: "number" } },
    { key: "ready", label: "Ready", value: counts.ready ?? 0, format: { kind: "number" } },
    { key: "exited", label: "Exited", value: counts.exited ?? 0, format: { kind: "number" } },
    { key: "torn_down", label: "Torn down", value: counts.torn_down ?? 0, format: { kind: "number" } },
  ];
}

export default async function SandboxesPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string }>;
}) {
  const sp = await searchParams;
  const state = sp.state ?? "";
  const sandboxes: SandboxRun[] = await listSandboxes(state || undefined);
  const stats = fleetStats(sandboxes);

  return (
    <>
      <SiteHeader active="sandboxes" />
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">Sandboxes</h1>
          <p className="text-sm text-muted-foreground">
            Every Docker container Noctua booted to run a mission — live, exited, or torn down.
          </p>
        </header>

        <StatsDisplay
          id="sandbox-fleet"
          title="Fleet"
          description={state ? `Filtered: ${state.replace(/_/g, " ")}` : "All sandboxes"}
          stats={stats}
        />

        <nav className="flex flex-wrap gap-1 border-b border-border">
          {STATE_FILTERS.map(f => {
            const active = f.key === state;
            return (
              <Link
                key={f.key || "all"}
                href={f.key ? `/sandboxes?state=${f.key}` : "/sandboxes"}
                className={
                  "px-3 py-1.5 text-sm rounded-t-md transition-colors " +
                  (active
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:text-foreground")
                }
              >
                {f.label}
              </Link>
            );
          })}
        </nav>

        {sandboxes.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-12 text-center space-y-1">
            <p className="text-sm text-foreground">No sandboxes here.</p>
            <p className="text-xs text-muted-foreground">
              {state
                ? "Try a different filter."
                : "When a mission boots a container, it lands here."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {sandboxes.map(s => (
              <SandboxCard key={s.id} sandbox={s} />
            ))}
          </div>
        )}
      </main>
    </>
  );
}
