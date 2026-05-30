import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { Artifact, ArtifactKind } from "@/lib/types";
import { artifactTitle, artifactSummary } from "@/lib/toolui-mappers";
import { ArtifactKindIcon, ArtifactKindLabel } from "@/lib/icons";
import CreatePRButton from "@/components/CreatePRButton";
import GitHubLinkBadge from "@/components/GitHubLinkBadge";

const KIND_TONE: Record<string, string> = {
  pr: "bg-violet-500/15 text-violet-300 ring-violet-500/30",
  tool: "bg-cyan-500/15 text-cyan-300 ring-cyan-500/30",
  social_post: "bg-pink-500/15 text-pink-300 ring-pink-500/30",
  analysis: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  diagnostic: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  cad: "bg-sky-500/15 text-sky-300 ring-sky-500/30",
};

export default function ArtifactCard({ artifact: a }: { artifact: Artifact }) {
  const title = artifactTitle(a);
  const snippet = artifactSummary(a);
  const tone = KIND_TONE[a.kind] ?? "bg-secondary text-muted-foreground";
  const Icon = ArtifactKindIcon[a.kind as ArtifactKind] ?? ArtifactKindIcon.tool;
  const label = ArtifactKindLabel[a.kind as ArtifactKind] ?? a.kind;

  const isPrWithoutUri = a.kind === "pr" && !a.uri;
  const isPrWithUri = a.kind === "pr" && !!a.uri;

  return (
    <Link
      href={`/queue/${a.id}`}
      className="group block rounded-lg border border-border bg-card/60 hover:bg-card hover:border-foreground/20 transition-colors p-4"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2 text-xs">
            <span
              className={`inline-flex items-center gap-1.5 px-1.5 py-0.5 rounded ring-1 uppercase tracking-wide ${tone}`}
              title={label}
            >
              <Icon className="h-3 w-3" strokeWidth={2.5} />
              {a.kind}
            </span>
            <span className="text-muted-foreground font-mono truncate">
              {a.producer_key}
            </span>
          </div>
          <div className="font-medium text-foreground/95 truncate">{title}</div>
          {snippet && (
            <div className="text-sm text-muted-foreground line-clamp-2">
              {snippet}
            </div>
          )}
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          {isPrWithoutUri && <CreatePRButton artifactId={a.id} />}
          {isPrWithUri && <GitHubLinkBadge href={a.uri} />}
          <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground group-hover:translate-x-0.5 transition-all" />
        </div>
      </div>
    </Link>
  );
}
