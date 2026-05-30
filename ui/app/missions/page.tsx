import Link from "next/link";
import { listMissions } from "@/lib/api";
import type { MissionListItem } from "@/lib/types";
import SiteHeader from "@/components/SiteHeader";
import { DataTable } from "@/components/tool-ui/data-table";
import { StatsDisplay } from "@/components/tool-ui/stats-display";
import { fleetStats } from "@/lib/toolui-mappers";
import type {
  Column,
  DataTableRowData,
} from "@/components/tool-ui/data-table";

const STATE_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "All" },
  { key: "running", label: "Running" },
  { key: "queued", label: "Queued" },
  { key: "needs_input", label: "Needs input" },
  { key: "succeeded", label: "Succeeded" },
  { key: "failed", label: "Failed" },
  { key: "stopped", label: "Stopped" },
];

type MissionRow = DataTableRowData & {
  id: number;
  state: string;
  producer: string;
  goal: string;
  tokens: number;
  tools: number;
  finished: string;
  href: string;
  reason: string;
};

const COLUMNS: Column<MissionRow>[] = [
  {
    key: "id",
    label: "#",
    width: "64px",
    align: "right",
    format: { kind: "number" },
  },
  {
    key: "state",
    label: "State",
    format: {
      kind: "status",
      statusMap: {
        queued: { tone: "neutral", label: "queued" },
        running: { tone: "info", label: "running" },
        succeeded: { tone: "success", label: "succeeded" },
        failed: { tone: "danger", label: "failed" },
        stopped: { tone: "warning", label: "stopped" },
        needs_input: { tone: "warning", label: "needs input" },
      },
    },
  },
  {
    key: "goal",
    label: "Goal",
    truncate: true,
    priority: "primary",
    format: { kind: "link", hrefKey: "href" },
  },
  {
    key: "producer",
    label: "Producer",
    hideOnMobile: true,
  },
  {
    key: "tokens",
    label: "Tokens",
    align: "right",
    format: { kind: "number", compact: true },
    hideOnMobile: true,
  },
  {
    key: "tools",
    label: "Tools",
    align: "right",
    format: { kind: "number" },
    hideOnMobile: true,
  },
  {
    key: "reason",
    label: "Stop reason",
    truncate: true,
    hideOnMobile: true,
  },
  {
    key: "finished",
    label: "Last seen",
    align: "right",
    format: { kind: "date", dateFormat: "relative" },
    hideOnMobile: true,
  },
];

export default async function MissionsPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string }>;
}) {
  const sp = await searchParams;
  const state = sp.state ?? "";
  const missions: MissionListItem[] = await listMissions(state || undefined);

  const stats = fleetStats(missions);
  const rows: MissionRow[] = missions.map(m => ({
    id: m.id,
    state: m.state,
    producer: m.producer_key,
    goal: m.goal,
    tokens: m.spent?.tokens ?? 0,
    tools: m.spent?.tool_calls ?? 0,
    finished: m.finished_at ?? m.created_at,
    href: `/missions/${m.id}`,
    reason: m.state_reason ?? "",
  }));

  return (
    <>
      <SiteHeader active="missions" />
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">Missions</h1>
          <p className="text-sm text-muted-foreground">
            Everything Noctua has tried — not just the ones with artifacts.
          </p>
        </header>

        <StatsDisplay
          id="fleet-stats"
          title="Fleet"
          description={state ? `Filtered: ${state.replace(/_/g, " ")}` : "All missions"}
          stats={stats}
        />

        <nav className="flex flex-wrap gap-1 border-b border-border">
          {STATE_FILTERS.map(f => {
            const active = f.key === state;
            return (
              <Link
                key={f.key || "all"}
                href={f.key ? `/missions?state=${f.key}` : "/missions"}
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

        <DataTable
          id="missions-table"
          columns={COLUMNS}
          data={rows}
          rowIdKey="id"
          defaultSort={{ by: "finished", direction: "desc" }}
          emptyMessage="No missions in this filter."
        />
      </main>
    </>
  );
}
