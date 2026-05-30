interface Props {
  source: string;
  size?: number;
  className?: string;
}

const ICON_SRC: Record<string, string> = {
  sentry: "/icons/sentry.svg",
};

const SOURCE_LABEL: Record<string, string> = {
  sentry: "Sentry",
  manual: "Manual",
};

export default function SourceIcon({ source, size = 14, className = "" }: Props) {
  const src = ICON_SRC[source];
  const label = SOURCE_LABEL[source] ?? source;
  if (!src) {
    return (
      <span className={`inline-flex items-center gap-1 text-muted-foreground ${className}`}>
        {label}
      </span>
    );
  }
  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      {/* Plain <img> — next/image's optimizer chokes on local SVGs under Turbopack, */}
      {/* and a 14px SVG gains nothing from optimization. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={`${label} logo`}
        width={size}
        height={size}
        className="shrink-0"
      />
      <span>{label}</span>
    </span>
  );
}
