import type {
  Artifact,
  Mission,
  MissionListItem,
  MissionState,
  Plan,
  PlanStep,
} from "./types";
import type { ProgressStep } from "@/components/tool-ui/progress-tracker";
import type { StatItem } from "@/components/tool-ui/stats-display";

type ExecPayload = { cmd?: string[]; cwd?: string };
type ToolPayload = { name?: string; args?: Record<string, unknown> };
type EditPayload = { goal?: string };

export function stepLabel(s: PlanStep): string {
  const p = s.payload as ExecPayload & ToolPayload & EditPayload;
  if (s.kind === "exec") {
    const head = p.cmd?.[0] ?? "exec";
    return `exec: ${head}`;
  }
  if (s.kind === "tool") return `tool: ${p.name ?? "<unnamed>"}`;
  if (s.kind === "edit") return p.goal ? `edit: ${p.goal.slice(0, 60)}` : "edit";
  return String(s.kind);
}

export function stepDescription(s: PlanStep): string | undefined {
  const p = s.payload as ExecPayload & ToolPayload & EditPayload;
  if (s.kind === "exec" && p.cmd) return p.cmd.join(" ");
  if (s.kind === "tool" && p.args) {
    const json = JSON.stringify(p.args);
    return json.length > 200 ? json.slice(0, 200) + "…" : json;
  }
  return undefined;
}

export function toProgressSteps(
  plan: Plan,
  missionState: MissionState,
): ProgressStep[] {
  let firstPendingMarked = false;
  return plan.steps.map((s, i) => {
    let status: ProgressStep["status"];
    if (s.status === "succeeded") status = "completed";
    else if (s.status === "failed") status = "failed";
    else if (s.status === "paused") status = "in-progress";
    else {
      const isActive =
        missionState === "running" && !firstPendingMarked;
      if (isActive) {
        firstPendingMarked = true;
        status = "in-progress";
      } else {
        status = "pending";
      }
    }
    return {
      id: s.step_id || `step-${i}`,
      label: stepLabel(s),
      description: stepDescription(s),
      status,
    };
  });
}

export function fleetStats(missions: MissionListItem[]): StatItem[] {
  const counts: Record<string, number> = {};
  let totalTokens = 0;
  let totalTools = 0;
  let stoppedByBudget = 0;
  for (const m of missions) {
    counts[m.state] = (counts[m.state] ?? 0) + 1;
    totalTokens += m.spent?.tokens ?? 0;
    totalTools += m.spent?.tool_calls ?? 0;
    if (m.state_reason?.startsWith("budget_exceeded")) stoppedByBudget += 1;
  }
  return [
    {
      key: "total",
      label: "Missions",
      value: missions.length,
      format: { kind: "number" },
    },
    {
      key: "running",
      label: "Running",
      value: counts.running ?? 0,
      format: { kind: "number" },
    },
    {
      key: "succeeded",
      label: "Succeeded",
      value: counts.succeeded ?? 0,
      format: { kind: "number" },
    },
    {
      key: "stopped_by_budget",
      label: "Stopped by budget",
      value: stoppedByBudget,
      format: { kind: "number" },
    },
    {
      key: "tokens",
      label: "Tokens",
      value: totalTokens,
      format: { kind: "number", compact: true },
    },
    {
      key: "tools",
      label: "Tool calls",
      value: totalTools,
      format: { kind: "number", compact: true },
    },
  ];
}

export interface ArtifactPreviewShape {
  title?: string;
  snippet?: string;
  diff?: string;
  patch?: string;
  files_changed?: number;
  additions?: number;
  deletions?: number;
  name?: string;
  text?: string;
  body?: string;
  author?: string;
  handle?: string;
  avatar_url?: string;
  url?: string;
  image_url?: string;
  language?: string;
  code?: string;
  summary?: string;
}

export function artifactTitle(a: Artifact): string {
  const p = a.preview as ArtifactPreviewShape;
  return p?.title ?? p?.name ?? a.uri ?? `artifact #${a.id}`;
}

export function artifactSummary(a: Artifact): string | undefined {
  const p = a.preview as ArtifactPreviewShape;
  return p?.snippet ?? p?.summary;
}
