"use client";

import { useTransition, useState } from "react";
import { useRouter } from "next/navigation";
import { createPullRequest } from "@/lib/api";

interface Props {
  artifactId: number;
}

export default function CreatePRButton({ artifactId }: Props) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const onClick = (e: React.MouseEvent) => {
    // Don't navigate to the detail page
    e.preventDefault();
    e.stopPropagation();
    setError(null);
    start(async () => {
      try {
        await createPullRequest(artifactId);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  };

  return (
    <div className="flex flex-col items-end gap-1" onClick={(e) => e.preventDefault()}>
      <button
        onClick={onClick}
        disabled={pending}
        className="shrink-0 rounded px-2 py-0.5 text-xs font-medium bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {pending ? "Queuing…" : "Open PR on GitHub"}
      </button>
      {error && (
        <span className="text-xs text-rose-400 max-w-[180px] text-right">{error}</span>
      )}
    </div>
  );
}
