"use client";

import { useState } from "react";
import { api, PromptImprovement, ReportPromptRef } from "@/lib/api";
import { useQuery } from "@/lib/useQuery";
import ScoreBadge from "./ScoreBadge";
import { Skeleton } from "./states";
import { CheckIcon, SparkIcon } from "./icons";

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
  const [copied, setCopied] = useState<string | null>(null);
  // Asking Claude costs a call, so it is opt-in per prompt rather than
  // happening automatically when the panel opens.
  const [wantLLM, setWantLLM] = useState(false);

  const { data, isLoading, error } = useQuery<PromptImprovement>(
    open ? `improve:${prompt.id}${wantLLM ? ":llm" : ""}` : null,
    () => api.improve(prompt.id, wantLLM),
    { staleMs: 300_000 },
  );

  async function copy(text: string, which: string) {
    await navigator.clipboard.writeText(text);
    setCopied(which);
    setTimeout(() => setCopied(null), 1800);
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
                  onClick={() => copy(data.rewrite, "template")}
                  className="inline-flex items-center gap-1 rounded border border-line-strong
                             px-1.5 py-0.5 text-2xs text-content-muted transition-colors
                             duration-200 ease-expo hover:bg-surface-hover hover:text-content"
                >
                  {copied === "template" ? (
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
                  fill — the template won&apos;t guess a file path or a reason it doesn&apos;t know.
                </p>
              )}

              {/* Optional: a full rewrite from Claude. The template above is
                  always available offline; this is the only LLM call here. */}
              {data.llm_rewrite ? (
                <div className="mt-4 border-t border-line pt-3">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <h4 className="eyebrow">Rewritten by Claude</h4>
                    <button
                      onClick={() => copy(data.llm_rewrite!.rewritten, "llm")}
                      className="inline-flex items-center gap-1 rounded border border-line-strong
                                 px-1.5 py-0.5 text-2xs text-content-muted transition-colors
                                 duration-200 ease-expo hover:bg-surface-hover hover:text-content"
                    >
                      {copied === "llm" ? (
                        <>
                          <CheckIcon width={11} height={11} /> Copied
                        </>
                      ) : (
                        "Copy"
                      )}
                    </button>
                  </div>
                  <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border
                                  border-accent-ring/40 bg-surface-raised p-3 font-mono
                                  text-2xs leading-relaxed text-content">
                    {data.llm_rewrite.rewritten}
                  </pre>
                  {data.llm_rewrite.what_changed.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {data.llm_rewrite.what_changed.map((c) => (
                        <li key={c} className="flex gap-1.5 text-2xs text-content-muted">
                          <CheckIcon width={11} height={11} className="mt-0.5 shrink-0 text-accent" />
                          {c}
                        </li>
                      ))}
                    </ul>
                  )}
                  {data.llm_rewrite.assumptions.length > 0 && (
                    <div className="mt-2 rounded bg-score-mid/10 px-2 py-1.5">
                      <p className="text-2xs font-medium text-score-mid">
                        Invented — check these before sending:
                      </p>
                      <ul className="mt-0.5 space-y-0.5">
                        {data.llm_rewrite.assumptions.map((a) => (
                          <li key={a} className="text-2xs text-content-muted">
                            · {a}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div className="mt-3 border-t border-line pt-3">
                  <button
                    onClick={() => setWantLLM(true)}
                    disabled={!data.llm_available || wantLLM}
                    title={
                      data.llm_available
                        ? undefined
                        : "Set ANTHROPIC_API_KEY and restart the backend"
                    }
                    className="inline-flex items-center gap-1.5 rounded-md border border-line-strong
                               px-2.5 py-1.5 text-2xs text-content-muted transition-colors
                               duration-200 ease-expo hover:bg-surface-hover hover:text-content
                               disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <SparkIcon width={12} height={12} />
                    {wantLLM ? "Rewriting…" : "Rewrite with Claude"}
                  </button>
                  {data.llm_error && (
                    <p className="mt-1.5 text-2xs text-score-low">{data.llm_error}</p>
                  )}
                </div>
              )}
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
