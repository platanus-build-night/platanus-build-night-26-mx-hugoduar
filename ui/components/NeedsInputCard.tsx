"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { respondToMission, cancelMission } from "@/lib/api";
import { ApprovalCard } from "@/components/tool-ui/approval-card";

interface Props {
  missionId: number;
  producerKey: string;
  prompt: string;
}

export default function NeedsInputCard({ missionId, producerKey, prompt }: Props) {
  const router = useRouter();
  const [response, setResponse] = useState("");
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const onConfirm = () => {
    setError(null);
    start(async () => {
      try {
        // If the user didn't type anything, "acknowledged" is the noop signal
        // that lets Claude resume with what it already knows.
        await respondToMission(missionId, response.trim() || "acknowledged — proceed with best judgement");
        router.refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    });
  };

  const onCancel = () => {
    setError(null);
    start(async () => {
      try {
        await cancelMission(missionId);
        router.refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    });
  };

  return (
    <div className="space-y-3">
      <ApprovalCard
        id={`mission-${missionId}-needs-input`}
        title="Mission is waiting on you"
        description={prompt}
        variant="default"
        confirmLabel={pending ? "Sending…" : "Acknowledged"}
        cancelLabel="Skip"
        metadata={[
          { key: "Mission", value: `#${missionId}` },
          { key: "Producer", value: producerKey },
        ]}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />
      <div className="max-w-md">
        <label
          htmlFor={`mission-${missionId}-response`}
          className="text-xs uppercase tracking-wide text-muted-foreground"
        >
          Optional response (sent to Claude on resume)
        </label>
        <textarea
          id={`mission-${missionId}-response`}
          value={response}
          onChange={(e) => setResponse(e.target.value)}
          placeholder="Leave blank to just acknowledge, or paste extra context…"
          className="mt-1 w-full min-h-[88px] rounded-md border border-border bg-secondary/40 p-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary"
          disabled={pending}
        />
        {error && (
          <p className="mt-2 text-xs text-rose-400">{error}</p>
        )}
      </div>
    </div>
  );
}
