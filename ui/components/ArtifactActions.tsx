"use client";
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { approveArtifact, rejectArtifact } from "@/lib/api";
import type { Artifact } from "@/lib/types";

export default function ArtifactActions({ artifact }: { artifact: Artifact }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  if (artifact.queue_state !== "pending") return null;

  const isTool = artifact.kind === "tool";
  return (
    <div className="mt-6 flex gap-3">
      <button
        disabled={pending}
        onClick={() => start(async () => { await approveArtifact(artifact.id); router.push("/queue"); router.refresh(); })}
        className="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50"
      >
        {isTool ? "Graduate" : "Approve"}
      </button>
      <button
        disabled={pending}
        onClick={() => start(async () => { await rejectArtifact(artifact.id); router.push("/queue"); router.refresh(); })}
        className="px-4 py-2 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50"
      >
        Reject
      </button>
    </div>
  );
}
