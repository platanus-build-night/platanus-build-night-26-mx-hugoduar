"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createPullRequest, getArtifact } from "@/lib/api";
import type { Artifact } from "@/lib/types";
import type { CreatePROverrides } from "@/lib/api";

export type CreatePRPhase = "idle" | "queued" | "working" | "done" | "failed";

interface State {
  phase: CreatePRPhase;
  prUrl: string | null;
  error: string | null;
}

const POLL_INTERVAL_MS = 3000;
const POLL_DEADLINE_MS = 120_000; // 2 minutes

/**
 * Triggers a manual PR creation and polls the artifact until the work
 * either completes (artifact.uri populated) or fails
 * (artifact.validation.create_pr_error populated). Surfaces phase + result
 * + error so the calling component can render any UI it wants.
 */
export function usePRCreation(artifactId: number) {
  const router = useRouter();
  const [state, setState] = useState<State>({
    phase: "idle",
    prUrl: null,
    error: null,
  });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelled = useRef(false);

  useEffect(() => {
    return () => {
      cancelled.current = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  const poll = useCallback(
    (deadline: number) => {
      const tick = async () => {
        if (cancelled.current) return;
        try {
          const a: Artifact = await getArtifact(artifactId);
          if (a.uri) {
            setState({ phase: "done", prUrl: a.uri, error: null });
            router.refresh();
            return;
          }
          const err = (a.validation as Record<string, unknown> | undefined)?.create_pr_error;
          if (err) {
            const msg = typeof err === "string" ? err : JSON.stringify(err);
            setState({ phase: "failed", prUrl: null, error: msg });
            router.refresh();
            return;
          }
          if (Date.now() > deadline) {
            setState({
              phase: "failed",
              prUrl: null,
              error:
                "Still running after 2 minutes. Check the Celery worker logs for noctua.runner.tasks.create_pr_for_artifact.",
            });
            return;
          }
          timer.current = setTimeout(tick, POLL_INTERVAL_MS);
        } catch (e) {
          setState({
            phase: "failed",
            prUrl: null,
            error: e instanceof Error ? e.message : String(e),
          });
        }
      };
      tick();
    },
    [artifactId, router],
  );

  const trigger = useCallback(
    async (overrides?: CreatePROverrides) => {
      setState({ phase: "queued", prUrl: null, error: null });
      try {
        await createPullRequest(artifactId, overrides);
        setState({ phase: "working", prUrl: null, error: null });
        poll(Date.now() + POLL_DEADLINE_MS);
      } catch (e) {
        setState({
          phase: "failed",
          prUrl: null,
          error: e instanceof Error ? e.message : String(e),
        });
      }
    },
    [artifactId, poll],
  );

  return { ...state, trigger };
}
