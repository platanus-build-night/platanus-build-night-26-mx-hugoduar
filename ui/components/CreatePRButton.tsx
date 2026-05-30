"use client";

import { Loader2, ExternalLink, CircleX, RotateCcw } from "lucide-react";
import GithubIcon from "@/components/GithubIcon";
import { usePRCreation } from "@/lib/usePRCreation";

interface Props {
  artifactId: number;
}

export default function CreatePRButton({ artifactId }: Props) {
  const { phase, prUrl, error, trigger } = usePRCreation(artifactId);

  // When the PR landed, swap to a "View on GitHub" link.
  if (phase === "done" && prUrl) {
    return (
      <a
        href={prUrl}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="inline-flex shrink-0 items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium bg-zinc-900 text-zinc-100 ring-1 ring-zinc-700 hover:bg-zinc-800"
      >
        <GithubIcon size={12} />
        View on GitHub
        <ExternalLink className="size-3" />
      </a>
    );
  }

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    trigger();
  };

  const busy = phase === "queued" || phase === "working";
  const failed = phase === "failed";

  let label: React.ReactNode;
  let className =
    "shrink-0 inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ";
  if (phase === "queued") {
    label = (
      <>
        <Loader2 className="size-3 animate-spin" />
        Queuing…
      </>
    );
    className += "bg-violet-600/70 text-white";
  } else if (phase === "working") {
    label = (
      <>
        <Loader2 className="size-3 animate-spin" />
        Working… (cloning, committing, opening PR)
      </>
    );
    className += "bg-violet-600/70 text-white";
  } else if (failed) {
    label = (
      <>
        <RotateCcw className="size-3" />
        Try again
      </>
    );
    className += "bg-rose-700 text-white hover:bg-rose-600";
  } else {
    label = (
      <>
        <GithubIcon size={12} />
        Open PR on GitHub
      </>
    );
    className += "bg-violet-600 text-white hover:bg-violet-500";
  }

  return (
    <div
      className="flex flex-col items-end gap-1"
      onClick={(e) => e.preventDefault()}
    >
      <button
        type="button"
        onClick={handleClick}
        disabled={busy}
        className={className}
        title={failed && error ? error : undefined}
      >
        {label}
      </button>
      {error && failed && (
        <span className="flex max-w-[220px] items-start gap-1 text-right text-xs text-rose-400">
          <CircleX className="mt-px size-3 shrink-0" />
          <span className="break-words">{error}</span>
        </span>
      )}
    </div>
  );
}
