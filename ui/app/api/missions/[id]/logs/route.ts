import { NextRequest } from "next/server";

// Allow long-lived streams (Next still defaults to streaming when we return a ReadableStream).
export const dynamic = "force-dynamic";
export const runtime = "nodejs"; // edge runtime has different fetch semantics for streams

const API = process.env.NOCTUA_API ?? "http://127.0.0.1:8000";
const TOKEN = process.env.NOCTUA_API_TOKEN ?? "";

export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  if (!TOKEN) {
    return new Response("server token not configured\n", { status: 500 });
  }

  const upstream = await fetch(`${API}/api/missions/${encodeURIComponent(id)}/logs`, {
    headers: { Authorization: `Bearer ${TOKEN}` },
    cache: "no-store",
    // Abort the upstream when the browser disconnects.
    signal: req.signal,
  });

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return new Response(
      `event: error\ndata: upstream ${upstream.status} ${upstream.statusText}${detail ? `\n${detail.slice(0, 300)}` : ""}\n\n`,
      {
        status: upstream.status === 401 ? 401 : 502,
        headers: { "Content-Type": "text/event-stream" },
      },
    );
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    },
  });
}
