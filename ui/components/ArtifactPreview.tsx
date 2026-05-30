import type { Artifact } from "@/lib/types";
import { CodeBlock } from "@/components/tool-ui/code-block";
import { CodeDiff } from "@/components/tool-ui/code-diff";
import { LinkedInPost } from "@/components/tool-ui/linkedin-post";
import { XPost } from "@/components/tool-ui/x-post";
import { InstagramPost } from "@/components/tool-ui/instagram-post";
import CadViewer, { type CadPreview, type CadValidation } from "@/components/CadViewer";

type PreviewShape = {
  title?: string;
  snippet?: string;
  text?: string;
  body?: string;
  patch?: string;
  diff?: string;
  language?: string;
  code?: string;
  platform?: "linkedin" | "x" | "twitter" | "instagram";
  author?: { name?: string; handle?: string; avatar_url?: string; headline?: string };
  image_url?: string;
};

function inferPlatform(
  title?: string,
  snippet?: string,
): "linkedin" | "x" | "instagram" | undefined {
  const text = `${title ?? ""} ${snippet ?? ""}`.toLowerCase();
  if (/\b(tweet|twitter|x[- ]post|x post)\b/.test(text)) return "x";
  if (/\b(instagram|reel|caption)\b/.test(text)) return "instagram";
  if (/\blinkedin\b/.test(text)) return "linkedin";
  return undefined;
}

function jsonBlock(id: string, value: unknown, language = "json") {
  return (
    <CodeBlock
      id={id}
      code={JSON.stringify(value, null, 2)}
      language={language}
      filename="preview"
      lineNumbers="hidden"
      maxCollapsedLines={20}
    />
  );
}

export default function ArtifactPreview({ artifact: a }: { artifact: Artifact }) {
  const p = (a.preview ?? {}) as PreviewShape;

  if (a.kind === "pr") {
    const patch = p.patch ?? p.diff;
    if (patch) {
      return (
        <CodeDiff
          id={`artifact-${a.id}-diff`}
          patch={patch}
          language={p.language ?? "diff"}
          filename={p.title}
          diffStyle="unified"
          lineNumbers="visible"
        />
      );
    }
    if (a.uri) {
      return (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="px-3 py-2 text-xs text-muted-foreground border-b border-border bg-card/50 flex items-center justify-between">
            <span className="font-mono">{a.uri}</span>
            <a
              href={a.uri}
              target="_blank"
              rel="noreferrer"
              className="hover:text-foreground underline-offset-2 hover:underline"
            >
              Open on GitHub ↗
            </a>
          </div>
          <iframe
            src={`${a.uri}/files`}
            className="w-full h-[60vh] bg-white"
            title="PR diff"
          />
        </div>
      );
    }
  }

  if (a.kind === "tool" && p.code) {
    return (
      <CodeBlock
        id={`artifact-${a.id}-code`}
        code={p.code}
        language={p.language ?? "python"}
        filename={p.title ?? a.uri}
        lineNumbers="visible"
      />
    );
  }

  if (a.kind === "social_post") {
    const text = p.text ?? p.body ?? p.snippet ?? "";
    const platform = p.platform ?? inferPlatform(p.title, p.snippet);
    const author = p.author ?? {};
    if (platform === "x" || platform === "twitter") {
      return (
        <XPost
          post={{
            id: String(a.id),
            author: {
              name: author.name ?? "Noctua",
              handle: author.handle ?? "@noctua",
              avatarUrl: author.avatar_url ?? "https://avatars.githubusercontent.com/u/0",
            },
            text,
            media: p.image_url
              ? { type: "image", url: p.image_url, alt: p.title ?? "post media" }
              : undefined,
          }}
        />
      );
    }
    if (platform === "instagram") {
      return (
        <InstagramPost
          post={{
            id: String(a.id),
            author: {
              name: author.name ?? "Noctua",
              handle: author.handle ?? "noctua",
              avatarUrl: author.avatar_url ?? "https://avatars.githubusercontent.com/u/0",
            },
            text,
            media: p.image_url
              ? [{ type: "image", url: p.image_url, alt: p.title ?? "post media" }]
              : undefined,
          }}
        />
      );
    }
    return (
      <LinkedInPost
        post={{
          id: String(a.id),
          author: {
            name: author.name ?? "Noctua",
            avatarUrl: author.avatar_url ?? "https://avatars.githubusercontent.com/u/0",
            headline: author.headline ?? "Overnight AI artifact factory",
          },
          text,
          media: p.image_url
            ? { type: "image", url: p.image_url, alt: p.title ?? "post media" }
            : undefined,
        }}
      />
    );
  }

  if (a.kind === "cad") {
    return (
      <CadViewer
        preview={a.preview as CadPreview}
        validation={a.validation as CadValidation}
      />
    );
  }

  if ((a.kind === "analysis" || a.kind === "diagnostic") && (p.text || p.body)) {
    return (
      <div className="rounded-lg border border-border bg-card/40 p-5 space-y-2">
        {p.title && <h3 className="font-semibold">{p.title}</h3>}
        <p className="text-sm text-foreground/90 whitespace-pre-wrap">
          {p.text ?? p.body}
        </p>
      </div>
    );
  }

  return jsonBlock(`artifact-${a.id}-preview`, a.preview);
}
