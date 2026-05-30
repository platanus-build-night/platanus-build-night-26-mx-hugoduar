import Link from "next/link";
import clsx from "clsx";

export default function TabBar({ tabs, active }: { tabs: { key: string; label: string }[]; active: string }) {
  return (
    <nav className="flex gap-2 border-b border-zinc-800">
      {tabs.map(t => (
        <Link key={t.key} href={`/queue?kind=${t.key}`}
          className={clsx("px-4 py-2 text-sm rounded-t",
            t.key === active ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200")}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
