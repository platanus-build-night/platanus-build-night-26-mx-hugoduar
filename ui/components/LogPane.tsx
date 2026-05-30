"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  missionId: number;
}

export default function LogPane({ missionId }: Props) {
  const [lines, setLines] = useState<string[]>([]);
  const [status, setStatus] = useState<"connecting" | "live" | "done" | "error" | "timeout">("connecting");
  const [doneState, setDoneState] = useState<string>("");
  const scrollRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const api = process.env.NEXT_PUBLIC_NOCTUA_API ?? "http://127.0.0.1:8000";
    const token = process.env.NEXT_PUBLIC_NOCTUA_TOKEN ?? "";
    const url = `${api}/api/missions/${missionId}/logs?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);

    es.onopen = () => setStatus("live");
    es.onmessage = (e) => {
      setLines((prev) => [...prev, e.data]);
    };
    es.addEventListener("done", (e) => {
      setStatus("done");
      setDoneState((e as MessageEvent).data ?? "");
      es.close();
    });
    es.addEventListener("error", (e) => {
      // EventSource fires "error" for both server-sent error events and connection errors.
      const data = (e as MessageEvent).data;
      if (typeof data === "string" && data) {
        setLines((prev) => [...prev, `[error] ${data}`]);
        setStatus("error");
        es.close();
      } else if (es.readyState === EventSource.CLOSED) {
        setStatus("error");
      }
    });
    es.addEventListener("timeout", () => {
      setStatus("timeout");
      es.close();
    });

    return () => {
      es.close();
    };
  }, [missionId]);

  useEffect(() => {
    // auto-scroll to bottom when new lines arrive
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [lines]);

  const badgeColor =
    status === "live" ? "bg-emerald-700 text-emerald-100" :
    status === "done" ? "bg-zinc-700 text-zinc-200" :
    status === "error" ? "bg-rose-800 text-rose-100" :
    status === "timeout" ? "bg-amber-700 text-amber-100" :
    "bg-zinc-800 text-zinc-300";

  return (
    <section className="mt-6">
      <div className="flex items-center gap-2 mb-2">
        <h2 className="text-sm uppercase tracking-wide text-zinc-400">Sandbox log</h2>
        <span className={`px-2 py-0.5 text-xs rounded ${badgeColor}`}>
          {status}{doneState ? `: ${doneState}` : ""}
        </span>
      </div>
      <pre
        ref={scrollRef}
        className="h-[40vh] overflow-y-auto p-3 rounded border border-zinc-800 bg-black text-xs font-mono text-zinc-200 whitespace-pre-wrap break-all"
      >
        {lines.length === 0 ? <span className="text-zinc-500">waiting for log output…</span> : lines.join("\n")}
      </pre>
    </section>
  );
}
