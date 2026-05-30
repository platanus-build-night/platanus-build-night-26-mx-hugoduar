import { getArtifact, getMission } from "@/lib/api";
import ArtifactActions from "@/components/ArtifactActions";
import SourceViewer from "@/components/SourceViewer";
import type { Artifact, Mission } from "@/lib/types";

export default async function DetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const artifact: Artifact = await getArtifact(Number(id));
  const mission: Mission = await getMission(artifact.mission_id);
  const planVersion = (artifact as any).provenance?.plan_version ?? "?";
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-8">
      <nav className="text-xs text-zinc-500 mb-4">
        <a href="/queue" className="hover:text-zinc-300">← Queue</a>
        <span className="mx-2">·</span>
        Mission #{mission.id} · {mission.goal} → Plan v{planVersion}
      </nav>
      <h1 className="text-2xl font-semibold">{(artifact.preview?.title as string) ?? artifact.uri}</h1>
      <div className="text-sm text-zinc-400 mt-1">{artifact.kind} · {artifact.queue_state}</div>

      {artifact.kind === "pr" && artifact.uri && (
        <iframe src={`${artifact.uri}/files`} className="w-full h-[60vh] mt-6 rounded border border-zinc-800 bg-white" />
      )}

      {artifact.kind === "tool" && (
        <SourceViewer artifactId={artifact.id} />
      )}

      <section className="mt-6 p-4 rounded border border-zinc-800">
        <h2 className="text-sm uppercase tracking-wide text-zinc-400">Validation</h2>
        <pre className="text-xs mt-2 overflow-x-auto">{JSON.stringify(artifact.validation, null, 2)}</pre>
      </section>

      <ArtifactActions artifact={artifact} />
    </main>
  );
}
