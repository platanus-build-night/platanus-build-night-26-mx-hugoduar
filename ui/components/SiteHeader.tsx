import Link from "next/link";

const NAV = [
  { href: "/queue", label: "Queue" },
  { href: "/missions", label: "Missions" },
  { href: "/sandboxes", label: "Sandboxes" },
  { href: "/signals", label: "Signals" },
];

export default function SiteHeader({ active }: { active: "queue" | "missions" | "sandboxes" | "signals" }) {
  return (
    <header className="border-b border-border bg-card/40">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/queue" className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
          <span className="font-semibold tracking-tight">Noctua</span>
          <span className="text-xs text-muted-foreground hidden sm:inline">
            overnight artifact factory
          </span>
        </Link>
        <nav className="flex gap-1">
          {NAV.map(n => {
            const isActive = n.href.includes(active);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={
                  "px-3 py-1.5 rounded-md text-sm transition-colors " +
                  (isActive
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/60")
                }
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
