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
  signal_id?: number | null;
}

export type SignalSource = "sentry" | "manual";
export type RoutingStatus = "pending" | "routed" | "ignored" | "failed";

export interface Signal {
  id: number;
  source: SignalSource;
  external_id: string;
  title: string;
  routing_status: RoutingStatus;
  routing_reason: string;
  received_at: string;
  mission_id?: number | null;
}

export interface SignalDetail extends Signal {
  payload: Record<string, unknown>;
}

export interface Producer {
  key: string;
  kind: string;
  rubric_md: string;
  version: number;
}

export interface MissionListItem {
  id: number;
  goal: string;
  state: MissionState;
  state_reason: string;
  producer_key: string;
  spent: Record<string, number>;
  budget: Record<string, number>;
  created_at: string;
  finished_at?: string | null;
}

export type SandboxState = "booting" | "ready" | "exited" | "torn_down";

export interface SandboxRun {
  id: number;
  mission_id: number;
  image_ref: string;
  container_id?: string | null;
  state: SandboxState;
  log_path: string;
  ttl_seconds: number;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface PlanStep {
  step_id: string;
  kind: "exec" | "tool" | "edit";
  payload: Record<string, unknown>;
  status: "pending" | "succeeded" | "failed" | "paused";
  attempt: number;
  result?: { ok?: boolean; value?: unknown; error?: string } | null;
}

export interface Plan {
  id: number;
  version: number;
  steps: PlanStep[];
  rendered_md: string;
}
