import Link from "next/link";
import { getSignalDetail } from "@/lib/api";
import type { SignalDetail, RoutingStatus } from "@/lib/types";
import SiteHeader from "@/components/SiteHeader";

const STATUS_COLOR: Record<RoutingStatus, string> = {
  routed: "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/30",
  ignored: "bg-secondary text-muted-foreground",
  failed: "bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/30",
  pending: "bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/30",
};

export default async function SignalDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const s: SignalDetail = await getSignalDetail(Number(id));

  return (
    <>
      <SiteHeader active="signals" />
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        <nav className="text-xs text-muted-foreground">
          <Link href="/signals" className="hover:text-foreground">
            ← Signals
          </Link>
        </nav>

        <header className="space-y-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>#{s.id}</span>
            <span>·</span>
            <span>{s.source}</span>
            <span>·</span>
            <span className="font-mono">{s.external_id}</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{s.title}</h1>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className={`px-2 py-0.5 rounded-md ${STATUS_COLOR[s.routing_status] ?? "bg-secondary"}`}>
              {s.routing_status}
            </span>
          </div>
          {s.routing_reason && (
            <p className="text-sm text-muted-foreground">{s.routing_reason}</p>
          )}
          {s.mission_id && (
            <p className="text-sm">
              Routed to{" "}
              <Link
                href={`/missions/${s.mission_id}`}
                className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2"
              >
                mission #{s.mission_id}
              </Link>
            </p>
          )}
        </header>

        <section className="rounded-lg border border-border p-4 space-y-2">
          <h2 className="text-xs uppercase tracking-wide text-muted-foreground">Raw payload</h2>
          <pre className="text-xs overflow-x-auto text-foreground/80">{JSON.stringify(s.payload, null, 2)}</pre>
        </section>
      </main>
    </>
  );
}
