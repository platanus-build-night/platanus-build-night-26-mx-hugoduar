"use client";
import { useState, useTransition } from "react";
import { Check, Pencil, Save, X } from "lucide-react";
import { updateRubric } from "@/lib/api";
import { CodeBlock } from "@/components/tool-ui/code-block";

export default function RubricEditor({
  producerKey,
  initial,
}: {
  producerKey: string;
  initial: string;
}) {
  const [text, setText] = useState(initial);
  const [editing, setEditing] = useState(false);
  const [pending, start] = useTransition();
  const [saved, setSaved] = useState(false);
  const dirty = text !== initial;

  return (
    <div className="mt-4 space-y-3">
      <div className="flex items-center gap-2">
        {!editing ? (
          <button
            onClick={() => {
              setEditing(true);
              setSaved(false);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-secondary hover:bg-secondary/80 text-sm transition-colors ring-1 ring-border"
          >
            <Pencil className="h-3.5 w-3.5" strokeWidth={2.25} />
            Edit
          </button>
        ) : (
          <>
            <button
              disabled={pending || !dirty}
              onClick={() =>
                start(async () => {
                  await updateRubric(producerKey, text);
                  setSaved(true);
                  setEditing(false);
                })
              }
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50 text-sm font-medium transition-colors"
            >
              <Save className="h-3.5 w-3.5" strokeWidth={2.5} />
              {pending ? "Saving…" : "Save"}
            </button>
            <button
              disabled={pending}
              onClick={() => {
                setText(initial);
                setEditing(false);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent hover:bg-secondary text-sm transition-colors ring-1 ring-border"
            >
              <X className="h-3.5 w-3.5" strokeWidth={2.25} />
              Cancel
            </button>
          </>
        )}
        {saved && !editing && (
          <span className="inline-flex items-center gap-1 text-sm text-emerald-400">
            <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
            Saved.
          </span>
        )}
        {dirty && editing && (
          <span className="text-xs text-amber-400">unsaved changes</span>
        )}
      </div>

      {editing ? (
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          className="w-full h-[60vh] font-mono text-sm bg-card border border-border rounded-lg p-4 focus:outline-none focus:ring-2 focus:ring-ring resize-y"
          spellCheck={false}
        />
      ) : (
        <CodeBlock
          id={`rubric-${producerKey}`}
          code={text}
          language="markdown"
          filename={`${producerKey}/rubric.md`}
          lineNumbers="visible"
        />
      )}
    </div>
  );
}
