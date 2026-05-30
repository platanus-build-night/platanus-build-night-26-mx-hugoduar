import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { getArtifact, getMission } from "@/lib/api";
import type { Artifact, ArtifactKind, Mission } from "@/lib/types";
import SiteHeader from "@/components/SiteHeader";
import ArtifactPreview from "@/components/ArtifactPreview";
import ArtifactApproval from "@/components/ArtifactApproval";
import CreatePRPanel from "@/components/CreatePRPanel";
import { CodeBlock } from "@/components/tool-ui/code-block";
import { artifactTitle } from "@/lib/toolui-mappers";
import { ArtifactKindIcon } from "@/lib/icons";

export default async function DetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const artifact: Artifact = await getArtifact(Number(id));
  const mission: Mission = await getMission(artifact.mission_id);
  const planVersion =
    (artifact as unknown as { provenance?: { plan_version?: string | number } })
      .provenance?.plan_version ?? "?";

  const title = artifactTitle(artifact);
  const validationKeys = Object.keys(artifact.validation ?? {});

  return (
    <>
      <SiteHeader active="queue" />
      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <nav className="text-xs text-muted-foreground">
          <Link href="/queue" className="hover:text-foreground">
            ← Queue
          </Link>
          <span className="mx-2">·</span>
          <Link
            href={`/missions/${mission.id}`}
            className="hover:text-foreground"
          >
            Mission #{mission.id}
          </Link>
          <span className="mx-2">·</span>
          <span>Plan v{planVersion}</span>
        </nav>

        <header className="space-y-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {(() => {
              const Icon = ArtifactKindIcon[artifact.kind as ArtifactKind];
              return (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-secondary text-foreground/80 uppercase tracking-wide">
                  {Icon && <Icon className="h-3 w-3" strokeWidth={2.5} />}
                  {artifact.kind}
                </span>
              );
            })()}
            <span className="font-mono">{artifact.producer_key}</span>
            <span>·</span>
            <span>{artifact.queue_state}</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="text-sm text-muted-foreground font-mono break-all">
            {artifact.uri}
          </p>
        </header>

        <section>
          {artifact.kind === "pr" && !artifact.uri ? (
            <CreatePRPanel artifactId={artifact.id} />
          ) : (
            <div className="space-y-2">
              {artifact.kind === "pr" && artifact.uri && (
                <div className="flex justify-end">
                  <a
                    href={artifact.uri}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-violet-400 hover:text-violet-300 underline-offset-2 hover:underline"
                  >
                    View on GitHub ↗
                  </a>
                </div>
              )}
              <ArtifactPreview artifact={artifact} />
            </div>
          )}
        </section>

        <ArtifactApproval
          artifact={artifact}
          metadata={[
            { key: "Mission", value: `#${mission.id} ${mission.goal}` },
            { key: "Producer", value: artifact.producer_key },
            { key: "Plan", value: `v${planVersion}` },
            ...(validationKeys.length > 0
              ? [{ key: "Checks", value: validationKeys.join(", ") }]
              : []),
          ]}
        />

        {Object.keys(artifact.validation ?? {}).length > 0 && (
          <section className="space-y-2">
            <h2 className="inline-flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5" strokeWidth={2.25} />
              Validation
            </h2>
            <CodeBlock
              id={`artifact-${artifact.id}-validation`}
              code={JSON.stringify(artifact.validation, null, 2)}
              language="json"
              lineNumbers="hidden"
              maxCollapsedLines={12}
            />
          </section>
        )}
      </main>
    </>
  );
}
