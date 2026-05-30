import Link from "next/link";
import { NavIcon } from "@/lib/icons";

const NAV = [
  { href: "/queue", label: "Queue", icon: NavIcon.queue },
  { href: "/missions", label: "Missions", icon: NavIcon.missions },
  { href: "/sandboxes", label: "Sandboxes", icon: NavIcon.sandboxes },
  { href: "/signals", label: "Signals", icon: NavIcon.signals },
  { href: "/connections", label: "Connections", icon: NavIcon.connections },
];

export default function SiteHeader({ active }: { active: "queue" | "missions" | "sandboxes" | "signals" | "connections" }) {
  return (
    <header className="border-b border-border bg-card/40">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/queue" className="flex items-center gap-2.5 group">
          <span className="relative inline-flex h-2.5 w-2.5">
            <span className="absolute inset-0 rounded-full bg-primary opacity-40 group-hover:animate-ping" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
          </span>
          <span className="font-semibold tracking-tight">Noctua</span>
          <span className="text-xs text-muted-foreground hidden sm:inline">
            overnight artifact factory
          </span>
        </Link>
        <nav className="flex gap-1">
          {NAV.map(n => {
            const isActive = n.href.includes(active);
            const Icon = n.icon;
            return (
              <Link
                key={n.href}
                href={n.href}
                className={
                  "px-3 py-1.5 rounded-md text-sm transition-colors inline-flex items-center gap-1.5 " +
                  (isActive
                    ? "bg-secondary text-foreground ring-1 ring-border shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/60")
                }
              >
                <Icon className="h-3.5 w-3.5" strokeWidth={2.25} />
                {n.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
