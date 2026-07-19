"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, PromptDetail } from "@/lib/api";
import ScoreBadge from "@/components/ScoreBadge";
import ScoreBreakdown from "@/components/ScoreBreakdown";
import NotesEditor from "@/components/NotesEditor";

function fileList(files: string[]) {
  return files.map((f) => f.split("/").slice(-2).join("/"));
}

export default function PromptPage({ params }: { params: { id: string } }) {
  const [p, setP] = useState<PromptDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.prompt(params.id).then(setP).catch((e) => setError(String(e)));
  }, [params.id]);

  if (error) return <div className="text-red-400">{error}</div>;
  if (!p) return <div className="text-neutral-500">Loading…</div>;

  const diffs = p.file_diffs;
  const hasDiffs =
    diffs.created.length || diffs.edited.length || diffs.deleted.length;

  return (
    <div>
      <Link
        href={`/sessions/${p.session_id}`}
        className="text-sm text-neutral-500 hover:text-neutral-300"
      >
        ← Back to session
      </Link>

      <div className="mt-3 flex items-center justify-between gap-4">
        <h1 className="text-lg font-semibold">Turn {p.turn_index}</h1>
        <ScoreBadge score={p.score?.overall ?? null} />
      </div>

      {/* Prompt text */}
      <section className="mt-5">
        <h2 className="text-xs uppercase tracking-wide text-neutral-500 mb-2">
          Prompt
        </h2>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 text-sm whitespace-pre-wrap">
          {p.text || (
            <span className="italic text-neutral-600">(no text captured)</span>
          )}
        </div>
      </section>

      {/* Score breakdown */}
      {p.score && (
        <section className="mt-6">
          <h2 className="text-xs uppercase tracking-wide text-neutral-500 mb-3">
            Score breakdown · scored by{" "}
            {p.score.model_phase >= 2 ? "ML model (MLP + rubric blend)" : "rubric"}
          </h2>
          <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
            <ScoreBreakdown factors={p.score.factors} />
          </div>
        </section>
      )}

      {/* What Claude did */}
      <section className="mt-6">
        <h2 className="text-xs uppercase tracking-wide text-neutral-500 mb-2">
          What Claude did
        </h2>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 text-sm space-y-2">
          <div className="text-neutral-400">
            {p.tool_calls.length} tool call
            {p.tool_calls.length !== 1 ? "s" : ""}
            {p.output_tokens != null &&
              ` · ${p.output_tokens.toLocaleString()} output tokens`}
            {p.model && ` · ${p.model}`}
          </div>
          {hasDiffs ? (
            <div className="space-y-1 font-mono text-xs">
              {fileList(diffs.created).map((f) => (
                <div key={f} className="text-emerald-400">+ {f}</div>
              ))}
              {fileList(diffs.edited).map((f) => (
                <div key={f} className="text-amber-400">~ {f}</div>
              ))}
              {fileList(diffs.deleted).map((f) => (
                <div key={f} className="text-red-400">- {f}</div>
              ))}
            </div>
          ) : (
            <div className="text-neutral-600 italic">No file changes.</div>
          )}
        </div>
      </section>

      {/* Notes */}
      <section className="mt-6">
        <h2 className="text-xs uppercase tracking-wide text-neutral-500 mb-2">
          Notes
        </h2>
        <NotesEditor
          promptId={p.id}
          initialNote={p.annotation?.note ?? null}
          initialTags={p.annotation?.tags ?? []}
        />
      </section>
    </div>
  );
}
