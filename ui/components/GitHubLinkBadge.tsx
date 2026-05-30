"use client";

export default function GitHubLinkBadge({ href }: { href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={(e) => e.stopPropagation()}
      className="shrink-0 rounded px-2 py-0.5 text-xs font-medium text-violet-300 ring-1 ring-violet-500/30 hover:bg-violet-500/20 transition-colors"
    >
      View on GitHub ↗
    </a>
  );
}
