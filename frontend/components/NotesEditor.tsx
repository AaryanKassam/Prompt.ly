"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { CheckIcon } from "./icons";

/**
 * Note + tag editor with an optimistic save.
 *
 * Saving a note succeeds essentially always, so the UI commits immediately and
 * only surfaces a failure if the request actually rejects — the button never
 * blocks on the round trip. The success marker clears itself after a moment.
 */
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
  const [status, setStatus] = useState<"idle" | "saved" | "error">("idle");
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(timer.current), []);

  async function save() {
    // Commit optimistically, then reconcile.
    setStatus("saved");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setStatus("idle"), 2000);

    try {
      await api.saveAnnotation(promptId, {
        note,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
    } catch {
      clearTimeout(timer.current);
      setStatus("error");
    }
  }

  const field =
    "w-full rounded-md border border-line bg-surface-raised px-3 py-2 text-sm " +
    "placeholder:text-content-faint transition-colors duration-200 ease-expo " +
    "focus:border-accent-ring focus:outline-none";

  return (
    <div className="space-y-2.5">
      <label className="block">
        <span className="sr-only">Note</span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="What made this prompt work, or not?"
          className={`${field} min-h-24 resize-y leading-relaxed`}
        />
      </label>

      <label className="block">
        <span className="sr-only">Tags</span>
        <input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="tags, comma, separated"
          className={field}
        />
      </label>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          className="h-11 rounded-md bg-accent px-4 text-sm font-medium text-canvas
                     transition-colors duration-200 ease-expo hover:bg-accent-hover"
        >
          Save note
        </button>

        {status === "saved" && (
          <span className="inline-flex items-center gap-1.5 text-sm text-accent">
            <CheckIcon width={15} height={15} />
            Saved
          </span>
        )}
        {status === "error" && (
          <span className="text-sm text-score-low">
            Couldn&apos;t save — is the backend running?
          </span>
        )}
      </div>
    </div>
  );
}
