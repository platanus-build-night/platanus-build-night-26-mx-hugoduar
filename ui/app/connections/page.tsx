import SiteHeader from "@/components/SiteHeader";
import ConnectionRow from "@/components/ConnectionRow";
import ConnectAnyToolkitForm from "@/components/ConnectAnyToolkitForm";
import { listConnections } from "@/lib/api";
import type { Connection } from "@/lib/types";

export default async function ConnectionsPage() {
  let connections: Connection[] = [];
  try {
    connections = await listConnections();
  } catch {
    // API may be down; render empty state gracefully
  }

  return (
    <>
      <SiteHeader active="connections" />
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">Connections</h1>
          <p className="text-sm text-muted-foreground">
            Composio toolkit OAuth connections used by producers to act on external services.
          </p>
        </header>

        {connections.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-12 text-center space-y-1">
            <p className="text-sm text-foreground">No connections yet.</p>
            <p className="text-xs text-muted-foreground">
              Connect a toolkit below to authorize Noctua to act on your behalf.
            </p>
          </div>
        ) : (
          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-secondary/40">
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Toolkit
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Status
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Connection ID
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Connected at
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Last error
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {connections.map(conn => (
                  <ConnectionRow key={conn.toolkit} conn={conn} />
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="rounded-lg border border-border bg-card/40 px-6 py-5">
          <ConnectAnyToolkitForm />
        </div>
      </main>
    </>
  );
}
