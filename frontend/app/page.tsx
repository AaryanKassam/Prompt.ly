"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, SessionSummary } from "@/lib/api";
import ScoreBadge from "@/components/ScoreBadge";

export default function HomePage() {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.sessions().then(setSessions).catch((e) => setError(String(e)));
  }, []);

  if (error)
    return (
      <div className="text-red-400">
        Could not reach the backend at the API URL. Is it running?
        <div className="text-neutral-500 text-sm mt-1">{error}</div>
      </div>
    );
  if (!sessions) return <div className="text-neutral-500">Loading…</div>;

  if (sessions.length === 0)
    return (
      <div className="text-neutral-400">
        No sessions yet. Run{" "}
        <code className="text-brand">python scripts/import_jsonl.py</code> to
        import your Claude Code history.
      </div>
    );

  return (
    <div>
      <h1 className="text-xl font-semibold mb-1">Sessions</h1>
      <p className="text-sm text-neutral-500 mb-6">
        {sessions.length} session{sessions.length !== 1 ? "s" : ""} tracked
      </p>
      <div className="space-y-2">
        {sessions.map((s) => (
          <Link
            key={s.id}
            href={`/sessions/${s.id}`}
            className="block rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 hover:border-neutral-700 hover:bg-neutral-900 transition"
          >
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <div className="font-medium truncate">{s.title}</div>
                <div className="text-xs text-neutral-500 mt-0.5 flex gap-3">
                  <span className="rounded bg-neutral-800 px-1.5 py-0.5">
                    {s.source}
                  </span>
                  <span>{s.prompt_count} prompts</span>
                  {s.created_at && (
                    <span>{new Date(s.created_at).toLocaleDateString()}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-xs text-neutral-500">avg</span>
                <ScoreBadge score={s.avg_score} />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
