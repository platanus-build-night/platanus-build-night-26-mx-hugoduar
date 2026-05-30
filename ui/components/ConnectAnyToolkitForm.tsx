"use client";
import { useRouter } from "next/navigation";
import { useTransition, useState } from "react";
import { initiateConnection } from "@/lib/api";

export default function ConnectAnyToolkitForm() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const trimmed = name.trim();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!trimmed) return;
    setError(null);
    start(async () => {
      try {
        const res = await initiateConnection(trimmed.toUpperCase());
        window.open(res.redirect_url, "_blank", "noopener,noreferrer");
        setName("");
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to initiate connection.");
      }
    });
  };

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium text-foreground">Add a toolkit</h2>
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <label htmlFor="toolkit-input" className="sr-only">Toolkit name</label>
        <input
          id="toolkit-input"
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="e.g. LINKEDIN"
          className="flex-1 max-w-xs px-3 py-1.5 text-sm rounded-md border border-border bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-border"
          disabled={pending}
        />
        <button
          type="submit"
          disabled={!trimmed || pending}
          className="px-3 py-1.5 text-sm rounded-md bg-secondary text-foreground hover:bg-secondary/80 transition-colors disabled:opacity-40 disabled:pointer-events-none"
        >
          {pending ? "Connecting…" : "Connect"}
        </button>
      </form>
      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}
      <p className="text-xs text-muted-foreground">
        Toolkit name is uppercased automatically. A new tab will open for OAuth.
      </p>
    </div>
  );
}
