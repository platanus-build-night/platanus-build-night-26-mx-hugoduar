"use client";

import { useState } from "react";
import { Loader2, ExternalLink, CircleCheck, CircleX } from "lucide-react";
import GithubIcon from "@/components/GithubIcon";
import { usePRCreation } from "@/lib/usePRCreation";
import type { CreatePROverrides } from "@/lib/api";

interface Props {
  artifactId: number;
}

const STEPS = [
  "Booting sandbox",
  "Cloning repo",
  "Creating branch",
  "Committing NOCTUA.md",
  "Pushing",
  "Opening draft PR",
];

export default function CreatePRPanel({ artifactId }: Props) {
  const { phase, prUrl, error, trigger } = usePRCreation(artifactId);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [branch, setBranch] = useState("");
  const [base, setBase] = useState("");

  const onSubmit = () => {
    const overrides: CreatePROverrides = {};
    if (title.trim()) overrides.title = title.trim();
    if (body.trim()) overrides.body = body.trim();
    if (branch.trim()) overrides.branch = branch.trim();
    if (base.trim()) overrides.base = base.trim();
    trigger(overrides);
  };

  const busy = phase === "queued" || phase === "working";
  const done = phase === "done" && prUrl;
  const failed = phase === "failed";

  return (
    <div className="rounded-lg border border-border bg-card/60 p-5 space-y-4">
      <div className="flex items-start gap-3">
        <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-zinc-900 text-zinc-100 ring-1 ring-zinc-700">
          <GithubIcon size={18} />
        </span>
        <div className="space-y-1">
          <h2 className="text-sm font-semibold">Create PR on GitHub</h2>
          <p className="text-xs text-muted-foreground">
            Opens a draft PR with a NOCTUA.md commit so this artifact has a
            real GitHub URL. All fields below are optional — defaults are
            derived from the artifact and mission.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="space-y-1 col-span-full">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Title
          </span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={`Noctua: review for artifact #${artifactId}`}
            disabled={busy}
            className="w-full rounded-md border border-border bg-secondary/40 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </label>

        <label className="space-y-1">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Branch
          </span>
          <input
            type="text"
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            placeholder={`noctua/artifact-${artifactId}`}
            disabled={busy}
            className="w-full rounded-md border border-border bg-secondary/40 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </label>

        <label className="space-y-1">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Base branch
          </span>
          <input
            type="text"
            value={base}
            onChange={(e) => setBase(e.target.value)}
            placeholder="main"
            disabled={busy}
            className="w-full rounded-md border border-border bg-secondary/40 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </label>

        <label className="space-y-1 col-span-full">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            PR body (optional override)
          </span>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Leave blank to use the auto-generated NOCTUA.md content."
            disabled={busy}
            className="w-full min-h-[80px] rounded-md border border-border bg-secondary/40 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </label>
      </div>

      {/* Action row — button + live status pill */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={onSubmit}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
        >
          {busy ? (
            <Loader2 className="size-4 animate-spin" />
          ) : done ? (
            <CircleCheck className="size-4" />
          ) : failed ? (
            <GithubIcon size={14} />
          ) : (
            <GithubIcon size={14} />
          )}
          {phase === "idle" && "Open Draft PR"}
          {phase === "queued" && "Queuing…"}
          {phase === "working" && "Working…"}
          {phase === "done" && "PR opened"}
          {phase === "failed" && "Try again"}
        </button>

        {phase === "working" && (
          <span className="text-xs text-muted-foreground">
            Sandbox is booting and gh is opening the PR. This can take ~60s on a cold image.
          </span>
        )}
      </div>

      {/* Progress hint while working */}
      {phase === "working" && (
        <ol className="space-y-1.5 rounded-md border border-border bg-secondary/30 p-3 text-xs text-muted-foreground">
          {STEPS.map((step) => (
            <li key={step} className="flex items-center gap-2">
              <Loader2 className="size-3 animate-spin text-violet-400" />
              {step}
            </li>
          ))}
          <li className="text-[10px] text-muted-foreground/70">
            (Steps run in order on the worker; we poll the artifact every 3s for the result.)
          </li>
        </ol>
      )}

      {/* Success */}
      {done && prUrl && (
        <div className="flex items-center gap-3 rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm">
          <CircleCheck className="size-5 text-emerald-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="font-medium text-emerald-200">PR opened</div>
            <a
              href={prUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-emerald-300 hover:text-emerald-200 break-all"
            >
              <GithubIcon size={12} />
              <span className="truncate">{prUrl}</span>
              <ExternalLink className="size-3 shrink-0" />
            </a>
          </div>
        </div>
      )}

      {/* Failure */}
      {failed && error && (
        <div className="flex items-start gap-3 rounded-md border border-rose-500/40 bg-rose-500/10 p-3 text-sm">
          <CircleX className="size-5 text-rose-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="font-medium text-rose-200">PR creation failed</div>
            <pre className="mt-1 whitespace-pre-wrap break-all text-xs text-rose-300/90">
              {error}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
