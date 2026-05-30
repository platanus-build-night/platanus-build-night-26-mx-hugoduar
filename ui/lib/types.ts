export type ArtifactKind = "pr" | "social_post" | "analysis" | "diagnostic" | "cad" | "tool";
export type QueueState = "pending" | "approved" | "rejected" | "promoted";
export type MissionState = "queued" | "running" | "succeeded" | "failed" | "stopped" | "needs_input";

export interface Artifact {
  id: number;
  mission_id: number;
  producer_key: string;
  kind: ArtifactKind;
  uri: string;
  preview: Record<string, unknown>;
  validation: Record<string, unknown>;
  queue_state: QueueState;
  tool_id?: number | null;
}

export interface Mission {
  id: number;
  goal: string;
  state: MissionState;
  state_reason: string;
  producer_key: string;
  repo_url: string;
  issue_url: string;
  budget: Record<string, number>;
  spent: Record<string, number>;
  needs_input_prompt?: string | null;
}

export interface Producer {
  key: string;
  kind: string;
  rubric_md: string;
  version: number;
}
