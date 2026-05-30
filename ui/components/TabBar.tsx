import Link from "next/link";
import clsx from "clsx";
import type { LucideIcon } from "lucide-react";

export default function TabBar({
  tabs,
  active,
}: {
  tabs: { key: string; label: string; count?: number; icon?: LucideIcon }[];
  active: string;
}) {
  return (
    <nav className="flex flex-wrap gap-1 border-b border-border">
      {tabs.map(t => {
        const isActive = t.key === active;
        const Icon = t.icon;
        return (
          <Link
            key={t.key}
            href={`/queue?kind=${t.key}`}
            className={clsx(
              "px-3 py-1.5 text-sm rounded-t-md transition-colors flex items-center gap-2",
              isActive
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary/50",
            )}
          >
            {Icon && <Icon className="h-3.5 w-3.5" strokeWidth={2.25} />}
            <span>{t.label}</span>
            {t.count !== undefined && t.count > 0 && (
              <span
                className={clsx(
                  "text-xs rounded-full px-1.5 py-0.5 leading-none",
                  isActive
                    ? "bg-foreground/15 text-foreground"
                    : "bg-secondary text-muted-foreground",
                )}
              >
                {t.count}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
