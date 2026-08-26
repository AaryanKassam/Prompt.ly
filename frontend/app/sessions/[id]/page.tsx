"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, SessionDetail } from "@/lib/api";
import ScoreBadge from "@/components/ScoreBadge";

function diffLabel(d: { created: number; edited: number; deleted: number }) {
  const parts: string[] = [];
  if (d.created) parts.push(`${d.created} created`);
  if (d.edited) parts.push(`${d.edited} edited`);
  if (d.deleted) parts.push(`${d.deleted} deleted`);
  return parts.join(" · ");
}

export default function SessionPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.session(params.id).then(setData).catch((e) => setError(String(e)));
  }, [params.id]);

  if (error) return <div className="text-red-400">{error}</div>;
  if (!data) return <div className="text-neutral-500">Loading…</div>;

  return (
    <div>
      <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-300">
        ← All sessions
      </Link>
      <div className="mt-3 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">{data.title}</h1>
          {data.project_path && (
            <div className="text-xs text-neutral-500 mt-1 font-mono">
              {data.project_path}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-neutral-500">session avg</span>
          <ScoreBadge score={data.avg_score} />
        </div>
      </div>

      <ol className="mt-6 space-y-3">
        {data.prompts.map((p) => (
          <li key={p.id}>
            <Link
              href={`/prompts/${p.id}`}
              className="block rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 hover:border-neutral-700 hover:bg-neutral-900 transition"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-xs text-neutral-500 mb-1">
                    Turn {p.turn_index}
                  </div>
                  <div className="text-sm text-neutral-200 line-clamp-2">
                    {p.text_preview || (
                      <span className="italic text-neutral-600">
                        (no text captured)
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-neutral-500 mt-2 flex flex-wrap gap-3">
                    {p.tool_count > 0 && <span>{p.tool_count} tool calls</span>}
                    {diffLabel(p.diffs) && <span>{diffLabel(p.diffs)}</span>}
                    {p.output_tokens != null && (
                      <span>{p.output_tokens.toLocaleString()} out tokens</span>
                    )}
                  </div>
                </div>
                <ScoreBadge score={p.overall} />
              </div>
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
