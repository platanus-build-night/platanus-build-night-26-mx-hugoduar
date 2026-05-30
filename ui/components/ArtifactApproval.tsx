"use client";
import { useTransition, useState } from "react";
import { useRouter } from "next/navigation";
import { approveArtifact, rejectArtifact } from "@/lib/api";
import { ApprovalCard } from "@/components/tool-ui/approval-card";
import type { Artifact } from "@/lib/types";

interface Props {
  artifact: Artifact;
  metadata?: { key: string; value: string }[];
}

export default function ArtifactApproval({ artifact, metadata }: Props) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [choice, setChoice] = useState<"approved" | "denied" | undefined>(
    artifact.queue_state === "approved" || artifact.queue_state === "promoted"
      ? "approved"
      : artifact.queue_state === "rejected"
      ? "denied"
      : undefined,
  );

  const isPending = artifact.queue_state === "pending";
  const isTool = artifact.kind === "tool";

  const onConfirm = () =>
    new Promise<void>(resolve =>
      start(async () => {
        await approveArtifact(artifact.id);
        setChoice("approved");
        router.refresh();
        resolve();
      }),
    );

  const onCancel = () =>
    new Promise<void>(resolve =>
      start(async () => {
        await rejectArtifact(artifact.id);
        setChoice("denied");
        router.refresh();
        resolve();
      }),
    );

  return (
    <div className={pending ? "opacity-70 pointer-events-none" : ""}>
      <ApprovalCard
        id={`artifact-${artifact.id}-approval`}
        title={isPending ? `Review this ${artifact.kind}` : `Decision: ${artifact.queue_state}`}
        description={
          isPending
            ? isTool
              ? "Graduate this tool into the registry so future missions can call it, or reject."
              : "Approve to ship this artifact, or reject to send it back."
            : `This artifact was ${artifact.queue_state}.`
        }
        variant="default"
        confirmLabel={isTool ? "Graduate" : "Approve"}
        cancelLabel="Reject"
        metadata={metadata}
        choice={choice}
        onConfirm={isPending ? onConfirm : undefined}
        onCancel={isPending ? onCancel : undefined}
      />
    </div>
  );
}
