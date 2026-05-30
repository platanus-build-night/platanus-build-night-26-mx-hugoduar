import { AlertTriangle, Shield, type LucideIcon } from "lucide-react";
import { BudgetIcon } from "@/lib/icons";
import type { Mission } from "@/lib/types";

const FIELDS: {
  key: "tokens" | "tool_calls" | "wall_seconds";
  label: string;
  fmt: (n: number) => string;
  Icon: LucideIcon;
}[] = [
  {
    key: "tokens",
    label: "Tokens",
    fmt: n => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}K` : String(n)),
    Icon: BudgetIcon.tokens,
  },
  {
    key: "tool_calls",
    label: "Tool calls",
    fmt: n => String(n),
    Icon: BudgetIcon.tool_calls,
  },
  {
    key: "wall_seconds",
    label: "Wall time",
    fmt: n => (n >= 60 ? `${Math.floor(n / 60)}m ${n % 60}s` : `${n}s`),
    Icon: BudgetIcon.wall_seconds,
  },
];

function breachField(reason: string | undefined | null): string | null {
  if (!reason) return null;
  const m = reason.match(/^budget_exceeded:\s*(\w+)/);
  return m ? m[1] : null;
}

function tone(pct: number, breached: boolean): { bar: string; text: string; ring: string } {
  if (breached) return { bar: "bg-rose-500", text: "text-rose-300", ring: "ring-rose-500/30" };
  if (pct >= 0.9) return { bar: "bg-amber-500", text: "text-amber-300", ring: "ring-amber-500/30" };
  if (pct >= 0.7) return { bar: "bg-yellow-500", text: "text-yellow-300", ring: "ring-yellow-500/30" };
  return { bar: "bg-emerald-500", text: "text-emerald-300", ring: "ring-emerald-500/30" };
}

export default function BudgetPanel({ mission }: { mission: Mission }) {
  const spent = mission.spent ?? {};
  const budget = mission.budget ?? {};
  const breached = breachField(mission.state_reason);

  const rows = FIELDS.map(f => {
    const used = (spent[f.key] as number | undefined) ?? 0;
    const cap = (budget[`max_${f.key}`] as number | undefined) ?? null;
    const pct = cap && cap > 0 ? used / cap : 0;
    const isBreached = breached === f.key || (cap !== null && used > cap);
    return { ...f, used, cap, pct, isBreached };
  });

  const stopped = mission.state === "stopped" && breached;

  return (
    <section className="rounded-lg border border-border bg-card/40">
      <header className="px-5 py-4 flex items-baseline justify-between border-b border-border">
        <div className="flex items-start gap-3">
          <Shield className="h-4 w-4 mt-0.5 text-muted-foreground" strokeWidth={2.25} />
          <div>
            <h2 className="font-semibold">Budget enforcer</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Mission is stopped when any usage exceeds its cap.
            </p>
          </div>
        </div>
        {stopped ? (
          <span className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded ring-1 ring-rose-500/40 bg-rose-500/15 text-rose-300">
            <AlertTriangle className="h-3.5 w-3.5" strokeWidth={2.25} />
            stopped · {breached} cap exceeded
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">monitoring</span>
        )}
      </header>
      <ul className="divide-y divide-border">
        {rows.map(r => {
          const t = tone(r.pct, r.isBreached);
          const noCap = r.cap === null;
          const pctClamped = Math.min(1, Math.max(0, r.pct));
          return (
            <li key={r.key} className="px-5 py-4 space-y-2">
              <div className="flex items-baseline justify-between gap-4">
                <div className="flex items-center gap-2">
                  <r.Icon className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={2.25} />
                  <span className="text-xs uppercase tracking-wide text-muted-foreground">
                    {r.label}
                  </span>
                  {r.isBreached && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ring-1 ${t.ring} ${t.text}`}>
                      EXCEEDED
                    </span>
                  )}
                </div>
                <div className="text-sm tabular-nums">
                  <span className={`font-medium ${r.isBreached ? t.text : "text-foreground"}`}>
                    {r.fmt(r.used)}
                  </span>
                  <span className="text-muted-foreground">
                    {" / "}
                    {noCap ? "∞" : r.fmt(r.cap as number)}
                  </span>
                </div>
              </div>
              <div className="h-2 rounded-full bg-secondary overflow-hidden">
                <div
                  className={`h-full transition-all ${noCap ? "bg-zinc-500" : t.bar}`}
                  style={{ width: noCap ? "8%" : `${pctClamped * 100}%` }}
                />
              </div>
              {!noCap && (
                <div className="text-xs text-muted-foreground tabular-nums">
                  {Math.round(r.pct * 100)}% used · {r.fmt(Math.max(0, (r.cap as number) - r.used))} headroom
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
