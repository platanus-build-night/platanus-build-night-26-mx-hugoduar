import Link from "next/link";
import type { Artifact } from "@/lib/types";

export default function ArtifactCard({ artifact: a }: { artifact: Artifact }) {
  const title = (a.preview?.title as string) ?? (a.preview?.name as string) ?? a.uri;
  const snippet = (a.preview?.snippet as string) ?? "";
  return (
    <Link href={`/queue/${a.id}`} className="block rounded border border-zinc-800 hover:border-zinc-600 bg-zinc-900 p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-zinc-500 uppercase">{a.kind} · {a.producer_key}</div>
          <div className="font-medium">{title}</div>
          {snippet && <div className="text-sm text-zinc-400 mt-1">{snippet}</div>}
        </div>
        <div className="text-xs text-zinc-500">{a.queue_state}</div>
      </div>
    </Link>
  );
}
