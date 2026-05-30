"use client";
import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { refreshConnection, disconnectConnection } from "@/lib/api";
import type { Connection, ConnectionStatus } from "@/lib/types";

const STATUS_CHIP: Record<ConnectionStatus, string> = {
  active: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  expired: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  revoked: "bg-secondary text-muted-foreground ring-border",
  pending: "bg-blue-500/15 text-blue-300 ring-blue-500/30",
};

export default function ConnectionRow({ conn }: { conn: Connection }) {
  const router = useRouter();
  const [pending, start] = useTransition();

  const handleRefresh = () =>
    start(async () => {
      await refreshConnection(conn.toolkit);
      router.refresh();
    });

  const handleDisconnect = () =>
    start(async () => {
      await disconnectConnection(conn.toolkit);
      router.refresh();
    });

  const chipClass =
    STATUS_CHIP[conn.status] ?? "bg-secondary text-muted-foreground ring-border";

  return (
    <tr
      className={
        "border-b border-border last:border-0 transition-opacity " +
        (pending ? "opacity-50 pointer-events-none" : "")
      }
    >
      <td className="px-4 py-3 font-mono text-sm text-foreground font-medium">
        {conn.toolkit}
      </td>
      <td className="px-4 py-3">
        <span
          className={`inline-flex items-center text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded ring-1 ${chipClass}`}
        >
          {conn.status}
        </span>
      </td>
      <td className="px-4 py-3 font-mono text-xs text-muted-foreground truncate max-w-[180px]">
        {conn.composio_conn_id || "—"}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">
        {conn.connected_at
          ? new Date(conn.connected_at).toLocaleString()
          : "—"}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground truncate max-w-[200px]">
        {conn.last_error || "—"}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            className="px-2 py-1 text-xs rounded-md bg-secondary text-foreground hover:bg-secondary/80 transition-colors"
          >
            Refresh
          </button>
          {conn.status === "active" && (
            <button
              onClick={handleDisconnect}
              className="px-2 py-1 text-xs rounded-md bg-secondary text-muted-foreground hover:text-foreground hover:bg-secondary/80 transition-colors"
            >
              Disconnect
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}
