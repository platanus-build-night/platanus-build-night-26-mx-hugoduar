import Link from "next/link";
import { Container, Cpu, Hash, Timer } from "lucide-react";
import { SandboxStateIcon } from "@/lib/icons";
import type { SandboxRun, SandboxState } from "@/lib/types";

const STATE_TONE: Record<SandboxState, { dot: string; chip: string }> = {
  booting: {
    dot: "bg-blue-400 animate-pulse",
    chip: "bg-blue-500/15 text-blue-300 ring-blue-500/30",
  },
  ready: {
    dot: "bg-emerald-400 animate-pulse",
    chip: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  },
  exited: {
    dot: "bg-amber-400",
    chip: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  },
  torn_down: {
    dot: "bg-zinc-500",
    chip: "bg-secondary text-muted-foreground ring-border",
  },
};

const STATE_LABEL: Record<SandboxState, string> = {
  booting: "booting",
  ready: "ready",
  exited: "exited",
  torn_down: "torn down",
};

function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function timeline(s: SandboxRun): { label: string; detail: string } {
  if (s.started_at && s.finished_at) {
    const start = new Date(s.started_at).getTime();
    const end = new Date(s.finished_at).getTime();
    const dur = Math.max(0, Math.round((end - start) / 1000));
    return {
      label: `ran ${fmtDuration(dur)}`,
      detail: new Date(s.finished_at).toLocaleString(),
    };
  }
  if (s.started_at) {
    return {
      label: "running",
      detail: new Date(s.started_at).toLocaleString(),
    };
  }
  return { label: "not started", detail: "—" };
}

interface Props {
  sandbox: SandboxRun;
  /** When true, hide the mission link (used inside a mission detail page). */
  hideMissionLink?: boolean;
}

export default function SandboxCard({ sandbox: s, hideMissionLink }: Props) {
  const tone = STATE_TONE[s.state] ?? STATE_TONE.torn_down;
  const tl = timeline(s);
  const short = s.container_id ? s.container_id.slice(0, 12) : null;
  const StateIcon = SandboxStateIcon[s.state] ?? SandboxStateIcon.torn_down;
  const isLive = s.state === "booting" || s.state === "ready";
  return (
    <article className="rounded-lg border border-border bg-card/40 hover:bg-card transition-colors">
      <div className="px-4 py-3 flex items-center justify-between gap-4 border-b border-border">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
          <span className="text-xs text-muted-foreground tabular-nums">
            #{s.id}
          </span>
          <span
            className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded ring-1 ${tone.chip}`}
          >
            <StateIcon
              className={`h-3 w-3 ${isLive && s.state === "booting" ? "animate-spin" : ""}`}
              strokeWidth={2.5}
            />
            {STATE_LABEL[s.state]}
          </span>
        </div>
        {!hideMissionLink && (
          <Link
            href={`/missions/${s.mission_id}`}
            className="text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline shrink-0"
          >
            mission #{s.mission_id} →
          </Link>
        )}
      </div>
      <dl className="px-4 py-3 space-y-1.5 text-xs">
        <div className="flex items-baseline gap-2">
          <dt className="w-20 shrink-0 text-muted-foreground inline-flex items-center gap-1.5">
            <Cpu className="h-3 w-3" strokeWidth={2.25} />
            image
          </dt>
          <dd className="font-mono text-foreground/90 truncate">
            {s.image_ref}
          </dd>
        </div>
        {short && (
          <div className="flex items-baseline gap-2">
            <dt className="w-20 shrink-0 text-muted-foreground inline-flex items-center gap-1.5">
              <Container className="h-3 w-3" strokeWidth={2.25} />
              container
            </dt>
            <dd className="font-mono text-foreground/70">{short}</dd>
          </div>
        )}
        <div className="flex items-baseline gap-2">
          <dt className="w-20 shrink-0 text-muted-foreground inline-flex items-center gap-1.5">
            <Hash className="h-3 w-3" strokeWidth={2.25} />
            ttl
          </dt>
          <dd className="font-mono text-foreground/70">
            {fmtDuration(s.ttl_seconds)}
          </dd>
        </div>
        <div className="flex items-baseline gap-2">
          <dt className="w-20 shrink-0 text-muted-foreground inline-flex items-center gap-1.5">
            <Timer className="h-3 w-3" strokeWidth={2.25} />
            {tl.label}
          </dt>
          <dd className="font-mono text-foreground/70">{tl.detail}</dd>
        </div>
      </dl>
    </article>
  );
}
