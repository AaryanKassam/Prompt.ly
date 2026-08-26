"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function NotesEditor({
  promptId,
  initialNote,
  initialTags,
}: {
  promptId: string;
  initialNote: string | null;
  initialTags: string[];
}) {
  const [note, setNote] = useState(initialNote ?? "");
  const [tags, setTags] = useState((initialTags ?? []).join(", "));
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">(
    "idle",
  );

  async function save() {
    setStatus("saving");
    try {
      await api.saveAnnotation(promptId, {
        note,
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      });
      setStatus("saved");
      setTimeout(() => setStatus("idle"), 1500);
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="space-y-3">
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Add a note about this prompt…"
        className="w-full rounded-lg bg-neutral-900 border border-neutral-800 p-3 text-sm focus:outline-none focus:ring-1 focus:ring-brand min-h-24"
      />
      <input
        value={tags}
        onChange={(e) => setTags(e.target.value)}
        placeholder="tags, comma, separated"
        className="w-full rounded-lg bg-neutral-900 border border-neutral-800 p-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand"
      />
      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={status === "saving"}
          className="rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {status === "saving" ? "Saving…" : "Save note"}
        </button>
        {status === "saved" && (
          <span className="text-sm text-emerald-400">Saved ✓</span>
        )}
        {status === "error" && (
          <span className="text-sm text-red-400">Failed to save</span>
        )}
      </div>
    </div>
  );
}
