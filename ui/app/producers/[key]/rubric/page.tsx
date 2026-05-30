import Link from "next/link";
import { getProducers } from "@/lib/api";
import RubricEditor from "@/components/RubricEditor";
import SiteHeader from "@/components/SiteHeader";
import type { Producer } from "@/lib/types";

export default async function RubricPage({
  params,
}: {
  params: Promise<{ key: string }>;
}) {
  const { key } = await params;
  const producers: Producer[] = await getProducers();
  const p = producers.find(x => x.key === key);
  if (!p) {
    return (
      <>
        <SiteHeader active="queue" />
        <main className="max-w-3xl mx-auto px-6 py-12 text-center text-muted-foreground">
          Producer <span className="font-mono">{key}</span> not found.
        </main>
      </>
    );
  }
  return (
    <>
      <SiteHeader active="queue" />
      <main className="max-w-4xl mx-auto px-6 py-8 space-y-4">
        <nav className="text-xs text-muted-foreground">
          <Link href="/queue" className="hover:text-foreground">
            ← Queue
          </Link>
        </nav>
        <header className="space-y-1">
          <div className="text-xs text-muted-foreground font-mono">
            producer · v{p.version}
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {p.key} <span className="text-muted-foreground">rubric</span>
          </h1>
          <p className="text-sm text-muted-foreground">
            Markdown rubric injected into the planner prompt for this producer.
          </p>
        </header>
        <RubricEditor producerKey={p.key} initial={p.rubric_md} />
      </main>
    </>
  );
}
