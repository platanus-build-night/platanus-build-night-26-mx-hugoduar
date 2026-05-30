import Link from "next/link";
import { GitPullRequest, ExternalLink, Radio, Boxes, ListChecks } from "lucide-react";
import { getMission, getMissionPlans, getMissionSandboxes } from "@/lib/api";
import type { Plan, Mission, PlanStep, SandboxRun, MissionState } from "@/lib/types";
import SiteHeader from "@/components/SiteHeader";
import LogPane from "@/components/LogPane";
import BudgetPanel from "@/components/BudgetPanel";
import SandboxCard from "@/components/SandboxCard";
import { toProgressSteps, stepLabel } from "@/lib/toolui-mappers";
import { ProgressTracker } from "@/components/tool-ui/progress-tracker";
import { Terminal } from "@/components/tool-ui/terminal";
import NeedsInputCard from "@/components/NeedsInputCard";
import { MissionStateIcon } from "@/lib/icons";

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
  const [mission, plans, sandboxes]: [Mission, Plan[], SandboxRun[]] = await Promise.all([
    getMission(missionId),
    getMissionPlans(missionId),
    getMissionSandboxes(missionId),
  ]);

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
                  className="inline-flex items-center gap-1 hover:text-foreground underline-offset-2 hover:underline"
                >
                  <GitPullRequest className="h-3 w-3" strokeWidth={2.25} />
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
                  className="inline-flex items-center gap-1 hover:text-foreground underline-offset-2 hover:underline"
                >
                  <ExternalLink className="h-3 w-3" strokeWidth={2.25} />
                  issue
                </a>
              </>
            )}
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {mission.goal}
          </h1>
          <div className="flex flex-wrap gap-2 text-xs">
            {(() => {
              const StateIcon = MissionStateIcon[mission.state as MissionState];
              return (
                <span
                  className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md ${
                    STATE_TONE[mission.state] ?? "bg-secondary"
                  }`}
                >
                  {StateIcon && (
                    <StateIcon
                      className={`h-3 w-3 ${mission.state === "running" ? "animate-spin" : ""}`}
                      strokeWidth={2.5}
                    />
                  )}
                  {mission.state}
                </span>
              );
            })()}
            {mission.state_reason && (
              <span className="px-2 py-0.5 rounded-md bg-rose-500/15 text-rose-300">
                {mission.state_reason}
              </span>
            )}
            {mission.signal_id && (
              <Link
                href={`/signals/${mission.signal_id}`}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/30 hover:bg-blue-500/30"
              >
                <Radio className="h-3 w-3" strokeWidth={2.25} />
                via signal #{mission.signal_id}
              </Link>
            )}
          </div>
        </header>

        <BudgetPanel mission={mission} />

        <section className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 className="inline-flex items-center gap-1.5 text-sm uppercase tracking-wide text-muted-foreground">
              <Boxes className="h-3.5 w-3.5" strokeWidth={2.25} />
              Sandboxes
            </h2>
            {sandboxes.length > 0 && (
              <span className="text-xs text-muted-foreground">
                {sandboxes.length} container{sandboxes.length === 1 ? "" : "s"}
              </span>
            )}
          </div>
          {sandboxes.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border p-6 text-center text-xs text-muted-foreground space-y-1">
              <p>No sandbox records for this mission.</p>
              <p className="text-[11px] opacity-70">
                Either this is a content-only producer (no sandbox needed) or
                the mission ran before sandbox tracking was added.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {sandboxes.map(s => (
                <SandboxCard key={s.id} sandbox={s} hideMissionLink />
              ))}
            </div>
          )}
        </section>

        {mission.needs_input_prompt && (
          <NeedsInputCard
            missionId={mission.id}
            producerKey={mission.producer_key}
            prompt={mission.needs_input_prompt}
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
                <h2 className="inline-flex items-center gap-1.5 text-sm uppercase tracking-wide text-muted-foreground">
                  <ListChecks className="h-3.5 w-3.5" strokeWidth={2.25} />
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

        {sandboxes.length > 0 && <LogPane missionId={mission.id} />}
      </main>
    </>
  );
}
