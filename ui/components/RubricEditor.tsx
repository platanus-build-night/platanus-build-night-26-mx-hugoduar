"use client";
import { useState, useTransition } from "react";
import { updateRubric } from "@/lib/api";

export default function RubricEditor({ producerKey, initial }: { producerKey: string; initial: string }) {
  const [text, setText] = useState(initial);
  const [pending, start] = useTransition();
  const [saved, setSaved] = useState(false);
  return (
    <div className="mt-4">
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        className="w-full h-[60vh] font-mono text-sm bg-zinc-900 border border-zinc-800 rounded p-3"
      />
      <div className="mt-3 flex gap-2 items-center">
        <button
          disabled={pending}
          onClick={() => start(async () => { await updateRubric(producerKey, text); setSaved(true); })}
          className="px-4 py-2 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50"
        >
          Save
        </button>
        {saved && <span className="text-sm text-emerald-400">Saved.</span>}
      </div>
    </div>
  );
}
