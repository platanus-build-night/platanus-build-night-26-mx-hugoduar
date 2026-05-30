import { getQueue } from "@/lib/api";
import TabBar from "@/components/TabBar";
import ArtifactCard from "@/components/ArtifactCard";
import SiteHeader from "@/components/SiteHeader";
import type { Artifact, ArtifactKind } from "@/lib/types";

const TABS: { key: ArtifactKind; label: string }[] = [
  { key: "pr", label: "Code" },
  { key: "tool", label: "Tools" },
  { key: "social_post", label: "Social" },
  { key: "analysis", label: "Clinical" },
  { key: "diagnostic", label: "Diagnostic" },
  { key: "cad", label: "CAD" },
];

export default async function QueuePage({
  searchParams,
}: {
  searchParams: Promise<{ kind?: string }>;
}) {
  const sp = await searchParams;
  const kind = sp.kind ?? "pr";

  const artifacts: Artifact[] = await getQueue(kind);
  const allCountsList = await Promise.all(
    TABS.map(async t => {
      if (t.key === kind) return { key: t.key, count: artifacts.filter(a => a.queue_state === "pending").length };
      const list: Artifact[] = await getQueue(t.key);
      return { key: t.key, count: list.filter(a => a.queue_state === "pending").length };
    }),
  );
  const counts = Object.fromEntries(allCountsList.map(c => [c.key, c.count]));

  const pending = artifacts.filter(a => a.queue_state === "pending");
  const approved = artifacts.filter(
    a => a.queue_state === "approved" || a.queue_state === "promoted",
  );

  const tabsWithCounts = TABS.map(t => ({ ...t, count: counts[t.key] }));

  return (
    <>
      <SiteHeader active="queue" />
      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            Last night&apos;s artifacts
          </h1>
          <p className="text-sm text-muted-foreground">
            Review what Noctua shipped while you slept. Approve to ship, reject
            to retry.
          </p>
        </header>

        <TabBar tabs={tabsWithCounts} active={kind} />

        <section className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm uppercase tracking-wide text-muted-foreground">
              Pending
            </h2>
            <span className="text-xs text-muted-foreground">
              {pending.length}
            </span>
          </div>
          {pending.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              Nothing pending here.
            </div>
          ) : (
            <div className="space-y-3">
              {pending.map(a => (
                <ArtifactCard key={a.id} artifact={a} />
              ))}
            </div>
          )}
        </section>

        {approved.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-baseline justify-between">
              <h2 className="text-sm uppercase tracking-wide text-muted-foreground">
                Recently shipped
              </h2>
              <span className="text-xs text-muted-foreground">
                {approved.length}
              </span>
            </div>
            <div className="space-y-3 opacity-70">
              {approved.map(a => (
                <ArtifactCard key={a.id} artifact={a} />
              ))}
            </div>
          </section>
        )}
      </main>
    </>
  );
}
