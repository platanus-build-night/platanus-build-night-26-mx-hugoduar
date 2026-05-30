import Link from "next/link";
import { getMission, getMissionPlans } from "@/lib/api";
import type { Plan, Mission, PlanStep } from "@/lib/types";
import SiteHeader from "@/components/SiteHeader";
import LogPane from "@/components/LogPane";
import {
  toProgressSteps,
  toBudgetStats,
  stepLabel,
} from "@/lib/toolui-mappers";
import { ProgressTracker } from "@/components/tool-ui/progress-tracker";
import { StatsDisplay } from "@/components/tool-ui/stats-display";
import { Terminal } from "@/components/tool-ui/terminal";
import { ApprovalCard } from "@/components/tool-ui/approval-card";

const STATE_TONE: Record<string, string> = {
  queued: "bg-secondary text-foreground",
  running: "bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/30",
  succeeded: "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/30",
  failed: "bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/30",
  stopped: "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/30",
  needs_input: "bg-fuchsia-500/20 text-fuchsia-300 ring-1 ring-fuchsia-500/30",
};

function FailedStepDetail({ step, index }: { step: PlanStep; index: number }) {
  const payload = step.payload as { cmd?: string[]; cwd?: string };
  const cmd =
    step.kind === "exec" && payload.cmd
      ? payload.cmd.join(" ")
      : stepLabel(step);
  const errorRaw = step.result?.error;
  const errorText =
    typeof errorRaw === "string"
      ? errorRaw
      : errorRaw
      ? JSON.stringify(errorRaw, null, 2)
      : "";
  return (
    <Terminal
      id={`failed-${step.step_id || index}`}
      command={cmd}
      stderr={errorText.slice(0, 4000)}
      exitCode={1}
      cwd={payload.cwd}
    />
  );
}

export default async function MissionDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const missionId = Number(id);
  const [mission, plans]: [Mission, Plan[]] = await Promise.all([
    getMission(missionId),
    getMissionPlans(missionId),
  ]);

  const budgetStats = toBudgetStats(mission.spent ?? {}, mission.budget ?? {});

  return (
    <>
      <SiteHeader active="missions" />
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        <nav className="text-xs text-muted-foreground">
          <Link href="/missions" className="hover:text-foreground">
            ← Missions
          </Link>
        </nav>

        <header className="space-y-3">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>#{mission.id}</span>
            <span>·</span>
            <span className="font-mono">{mission.producer_key}</span>
            {mission.repo_url && (
              <>
                <span>·</span>
                <a
                  href={mission.repo_url}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-foreground underline-offset-2 hover:underline"
                >
                  repo
                </a>
              </>
            )}
            {mission.issue_url && (
              <>
                <span>·</span>
                <a
                  href={mission.issue_url}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-foreground underline-offset-2 hover:underline"
                >
                  issue
                </a>
              </>
            )}
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {mission.goal}
          </h1>
          <div className="flex flex-wrap gap-2 text-xs">
            <span
              className={`px-2 py-0.5 rounded-md ${
                STATE_TONE[mission.state] ?? "bg-secondary"
              }`}
            >
              {mission.state}
            </span>
            {mission.state_reason && (
              <span className="px-2 py-0.5 rounded-md bg-rose-500/15 text-rose-300">
                {mission.state_reason}
              </span>
            )}
          </div>
        </header>

        {budgetStats.length > 0 && (
          <StatsDisplay
            id={`mission-${mission.id}-budget`}
            title="Budget"
            description="What this mission has spent against its cap."
            stats={budgetStats}
          />
        )}

        {mission.needs_input_prompt && (
          <ApprovalCard
            id={`mission-${mission.id}-needs-input`}
            title="Mission is waiting on you"
            description={mission.needs_input_prompt}
            variant="default"
            confirmLabel="Acknowledged"
            cancelLabel="Skip"
            metadata={[
              { key: "Mission", value: `#${mission.id}` },
              { key: "Producer", value: mission.producer_key },
            ]}
          />
        )}

        {plans.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No plans were emitted for this mission yet.
          </p>
        )}

        {plans.map(p => {
          const steps = toProgressSteps(p, mission.state);
          const failedSteps = p.steps
            .map((s, idx) => ({ s, idx }))
            .filter(({ s }) => s.status === "failed");
          return (
            <section key={p.id} className="space-y-4">
              <div className="flex items-baseline justify-between">
                <h2 className="text-sm uppercase tracking-wide text-muted-foreground">
                  Plan v{p.version}
                </h2>
                <span className="text-xs text-muted-foreground">
                  {p.steps.length} step{p.steps.length === 1 ? "" : "s"}
                </span>
              </div>
              <ProgressTracker
                id={`plan-${p.id}`}
                steps={steps}
              />
              {failedSteps.length > 0 && (
                <div className="space-y-3 pt-2">
                  <h3 className="text-xs uppercase tracking-wide text-rose-300/80">
                    Failures
                  </h3>
                  {failedSteps.map(({ s, idx }) => (
                    <FailedStepDetail
                      key={s.step_id ?? idx}
                      step={s}
                      index={idx}
                    />
                  ))}
                </div>
              )}
            </section>
          );
        })}

        <LogPane missionId={mission.id} />
      </main>
    </>
  );
}
