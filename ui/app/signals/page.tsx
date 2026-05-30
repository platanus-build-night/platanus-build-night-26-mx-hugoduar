import Link from "next/link";
import { listSignals } from "@/lib/api";
import type { Signal, RoutingStatus } from "@/lib/types";
import SiteHeader from "@/components/SiteHeader";
import SourceIcon from "@/components/SourceIcon";

const STATUS_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "All" },
  { key: "routed", label: "Routed" },
  { key: "ignored", label: "Ignored" },
  { key: "failed", label: "Failed" },
  { key: "pending", label: "Pending" },
];

const STATUS_COLOR: Record<RoutingStatus, string> = {
  routed: "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/30",
  ignored: "bg-secondary text-muted-foreground",
  failed: "bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/30",
  pending: "bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/30",
};

function fmt(ts?: string) {
  if (!ts) return "—";
  return new Date(ts).toLocaleString();
}

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ status?: string }> }) {
  const sp = await searchParams;
  const status = sp.status ?? "";
  const signals: Signal[] = await listSignals(status || undefined);

  return (
    <>
      <SiteHeader active="signals" />
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">Signals</h1>
          <p className="text-sm text-muted-foreground">
            External events that can spawn missions. Use{" "}
            <code className="text-foreground bg-secondary px-1 rounded text-xs">
              ./manage.py mock_sentry_issue
            </code>{" "}
            to inject a fake Sentry error.
          </p>
        </header>

        <nav className="flex flex-wrap gap-1 border-b border-border">
          {STATUS_FILTERS.map(f => {
            const active = f.key === status;
            return (
              <Link
                key={f.key || "all"}
                href={f.key ? `/signals?status=${f.key}` : "/signals"}
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

        <div className="space-y-2">
          {signals.length === 0 && (
            <p className="text-sm text-muted-foreground">No signals in this filter.</p>
          )}
          {signals.map(s => (
            <Link
              key={s.id}
              href={`/signals/${s.id}`}
              className="block rounded-lg border border-border hover:border-muted-foreground/40 bg-card p-4 transition-colors"
            >
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-muted-foreground">#{s.id}</span>
                    <span className={`px-2 py-0.5 rounded-md ${STATUS_COLOR[s.routing_status] ?? "bg-secondary"}`}>
                      {s.routing_status}
                    </span>
                    <SourceIcon source={s.source} className="text-muted-foreground" />
                    <span className="text-border">·</span>
                    <span className="text-muted-foreground font-mono">{s.external_id}</span>
                  </div>
                  <div className="font-medium mt-1 truncate">{s.title}</div>
                  {s.routing_reason && (
                    <div className={`text-xs mt-1 ${s.routing_status === "ignored" ? "text-muted-foreground" : "text-muted-foreground/70"}`}>
                      {s.routing_reason}
                    </div>
                  )}
                </div>
                <div className="text-right text-xs text-muted-foreground shrink-0">
                  <div>{fmt(s.received_at)}</div>
                  {s.mission_id && (
                    <div className="mt-1 text-emerald-400">mission #{s.mission_id}</div>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      </main>
    </>
  );
}
