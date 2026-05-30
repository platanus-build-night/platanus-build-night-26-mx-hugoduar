import Image from "next/image";

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
      <Image
        src={src}
        alt={`${label} logo`}
        width={size}
        height={size}
        className="shrink-0"
        unoptimized
      />
      <span>{label}</span>
    </span>
  );
}
