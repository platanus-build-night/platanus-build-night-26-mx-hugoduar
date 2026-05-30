import {
  Activity,
  Archive,
  Box,
  Boxes,
  CheckCircle2,
  CircleHelp,
  Clock,
  ExternalLink,
  FlaskConical,
  GitPullRequest,
  Hammer,
  Inbox,
  Loader2,
  MessageSquareText,
  OctagonPause,
  Pencil,
  Plug,
  Radio,
  Save,
  Sparkles,
  Square,
  Stethoscope,
  Target,
  Timer,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";
import type { ArtifactKind, MissionState, SandboxState } from "@/lib/types";

export const ArtifactKindIcon: Record<ArtifactKind, LucideIcon> = {
  pr: GitPullRequest,
  tool: Hammer,
  social_post: MessageSquareText,
  analysis: FlaskConical,
  diagnostic: Stethoscope,
  cad: Box,
};

export const ArtifactKindLabel: Record<ArtifactKind, string> = {
  pr: "Pull request",
  tool: "Tool",
  social_post: "Social post",
  analysis: "Clinical analysis",
  diagnostic: "Diagnostic",
  cad: "CAD part",
};

export const MissionStateIcon: Record<MissionState, LucideIcon> = {
  queued: Clock,
  running: Loader2,
  succeeded: CheckCircle2,
  failed: X,
  stopped: OctagonPause,
  needs_input: CircleHelp,
};

export const SandboxStateIcon: Record<SandboxState, LucideIcon> = {
  booting: Loader2,
  ready: Activity,
  exited: Square,
  torn_down: Archive,
};

export const NavIcon = {
  queue: Inbox,
  missions: Target,
  sandboxes: Boxes,
  signals: Radio,
  connections: Plug,
} as const;

export const BudgetIcon = {
  tokens: Sparkles,
  tool_calls: Wrench,
  wall_seconds: Timer,
} as const;

export const ActionIcon = {
  edit: Pencil,
  save: Save,
  external: ExternalLink,
} as const;
