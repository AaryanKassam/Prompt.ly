"use client";

import { useState } from "react";
import { api, PromptImprovement, ReportPromptRef } from "@/lib/api";
import { useQuery } from "@/lib/useQuery";
import ScoreBadge from "./ScoreBadge";
import { Skeleton } from "./states";
import { CheckIcon } from "./icons";

/**
 * A low-scoring prompt with an "IMP" toggle that explains what went wrong and
 * drafts a stronger version.
 *
 * The rewrite is assembled from the user's own words plus bracketed slots — it
 * never invents a file path or a rationale. That is stated in the UI, because a
 * rewrite that looked authoritative while being fiction would be worse than no
 * rewrite at all.
 */
export default function ImprovePanel({ prompt }: { prompt: ReportPromptRef }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data, isLoading, error } = useQuery<PromptImprovement>(
    open ? `improve:${prompt.id}` : null,
    () => api.improve(prompt.id),
    { staleMs: 300_000 },
  );

  async function copy() {
    if (!data) return;
    await navigator.clipboard.writeText(data.rewrite);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  return (
    <div className="card p-3.5">
      <div className="flex items-start gap-3">
        <ScoreBadge score={prompt.score} size="sm" />
        <p className="min-w-0 flex-1 text-sm leading-relaxed text-content-muted">
          {prompt.preview}
        </p>
      </div>

      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="mt-2.5 rounded-md border border-line-strong px-2 py-1 text-2xs
                   font-semibold tracking-wide text-content-muted transition-colors
                   duration-200 ease-expo hover:bg-surface-hover hover:text-content"
      >
        {open ? "HIDE" : "IMP"}
      </button>

      {open && (
        <div className="mt-3 border-t border-line pt-3">
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-3 w-1/3" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          ) : error ? (
            <p className="text-sm text-score-low">{error.message}</p>
          ) : data ? (
            <>
              <h4 className="eyebrow mb-2">
                What&apos;s wrong · {data.issue_count} issue
                {data.issue_count === 1 ? "" : "s"}
              </h4>
              <ul className="space-y-1.5">
                {data.issues.slice(0, 6).map((issue) => (
                  <li key={issue.signal} className="text-sm leading-relaxed">
                    <span className="font-medium text-score-mid">{issue.label}</span>
                    <span className="text-content-muted"> — {issue.why}</span>
                  </li>
                ))}
              </ul>

              <div className="mb-2 mt-4 flex items-center justify-between gap-3">
                <h4 className="eyebrow">Stronger version</h4>
                <button
                  onClick={copy}
                  className="inline-flex items-center gap-1 rounded border border-line-strong
                             px-1.5 py-0.5 text-2xs text-content-muted transition-colors
                             duration-200 ease-expo hover:bg-surface-hover hover:text-content"
                >
                  {copied ? (
                    <>
                      <CheckIcon width={11} height={11} /> Copied
                    </>
                  ) : (
                    "Copy"
                  )}
                </button>
              </div>
              <pre
                className="overflow-x-auto whitespace-pre-wrap rounded-md border border-line
                           bg-surface-raised p-3 font-mono text-2xs leading-relaxed text-content"
              >
                {data.rewrite}
              </pre>
              {data.slots > 0 && (
                <p className="mt-1.5 text-2xs text-content-faint">
                  {data.slots} bracketed slot{data.slots === 1 ? "" : "s"} left for you to
                  fill — Prompt.ly won&apos;t guess a file path or a reason it doesn&apos;t know.
                </p>
              )}
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
