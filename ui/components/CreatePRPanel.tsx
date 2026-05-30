"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createPullRequest } from "@/lib/api";
import type { CreatePROverrides } from "@/lib/api";

interface Props {
  artifactId: number;
}

export default function CreatePRPanel({ artifactId }: Props) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [branch, setBranch] = useState("");
  const [base, setBase] = useState("");

  const onSubmit = () => {
    setError(null);
    start(async () => {
      try {
        const overrides: CreatePROverrides = {};
        if (title.trim()) overrides.title = title.trim();
        if (body.trim()) overrides.body = body.trim();
        if (branch.trim()) overrides.branch = branch.trim();
        if (base.trim()) overrides.base = base.trim();
        await createPullRequest(artifactId, overrides);
        router.refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    });
  };

  return (
    <div className="rounded-lg border border-border bg-card/60 p-5 space-y-4">
      <div className="space-y-1">
        <h2 className="text-sm font-semibold">Create PR on GitHub</h2>
        <p className="text-xs text-muted-foreground">
          Opens a draft PR with a NOCTUA.md commit so this artifact has a real
          GitHub URL. All fields are optional — defaults are derived from the
          artifact and mission.
        </p>
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
            disabled={pending}
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
            disabled={pending}
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
            disabled={pending}
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
            disabled={pending}
            className="w-full min-h-[80px] rounded-md border border-border bg-secondary/40 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </label>
      </div>

      {error && (
        <p className="text-xs text-rose-400 break-all">{error}</p>
      )}

      <button
        onClick={onSubmit}
        disabled={pending}
        className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {pending ? "Queuing…" : "Open Draft PR"}
      </button>
    </div>
  );
}
