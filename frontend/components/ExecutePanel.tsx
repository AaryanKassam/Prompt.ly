"use client";

import { useState } from "react";
import { api, Playbook, PlaybookRewrite, Recommendation } from "@/lib/api";
import { primeCache, useQuery } from "@/lib/useQuery";
import { Skeleton } from "./states";
import ScoreBadge from "./ScoreBadge";
import { CheckIcon, ChevronRightIcon, RefreshIcon, SparkIcon } from "./icons";

/**
 * Personalised prompting playbook.
 *
 * Refresh is deliberately manual and only offered once prompts have actually
 * accumulated: generating costs an API call, so the button reports how many
 * prompts are new and lets the user decide whether that is worth spending on.
 * An always-available "Regenerate" mostly produced the same advice for money.
 */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      }}
      className="inline-flex shrink-0 items-center gap-1 rounded border border-line-strong
                 px-2 py-1 text-2xs text-content-muted transition-colors duration-200
                 ease-expo hover:bg-surface-hover hover:text-content"
    >
      {copied ? (
        <>
          <CheckIcon width={11} height={11} /> Copied
        </>
      ) : (
        "Copy"
      )}
    </button>
  );
}

/** One prompt, collapsed to its label; expands to the rewrite. */
function RewriteCard({ rewrite }: { rewrite: PlaybookRewrite }) {
  const [open, setOpen] = useState(false);

  return (
    <li className="overflow-hidden rounded-lg border border-line bg-surface/60">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-3.5 py-3 text-left
                   transition-colors duration-200 ease-expo hover:bg-surface-raised"
      >
        <ChevronRightIcon
          width={14}
          height={14}
          className={`shrink-0 text-content-faint transition-transform duration-200
                      ease-expo ${open ? "rotate-90" : ""}`}
        />
        {rewrite.score != null && <ScoreBadge score={rewrite.score} size="sm" />}
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{rewrite.label}</span>
          {rewrite.original && (
            <span className="mt-0.5 block truncate text-2xs text-content-subtle">
              {rewrite.original}
            </span>
          )}
        </span>
        <span className="shrink-0 text-2xs text-content-faint">
          {open ? "Hide" : "Improve"}
        </span>
      </button>

      {open && (
        <div className="border-t border-line px-3.5 pb-3.5 pt-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h4 className="eyebrow">Rewritten</h4>
            <CopyButton text={rewrite.rewritten} />
          </div>

          {/* Readability first: near-white text on a lighter panel, generous
              line-height, and a normal reading size rather than the 11px used
              for dense metadata elsewhere. */}
          <pre
            className="overflow-x-auto whitespace-pre-wrap rounded-md border border-line-strong
                       bg-[#1B2436] p-4 font-mono text-[13px] leading-[1.75] text-[#E8EDF5]"
          >
            {rewrite.rewritten}
          </pre>

          <p className="mt-2.5 text-[13px] leading-relaxed text-content-muted">
            {rewrite.why}
          </p>

          {rewrite.fixes?.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {rewrite.fixes.map((f) => (
                <li
                  key={f}
                  className="rounded bg-accent-soft px-1.5 py-0.5 text-2xs text-accent"
                >
                  {f}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

export default function ExecutePanel({
  recommendations,
  path,
}: {
  recommendations: Recommendation[];
  path?: string;
}) {
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = path ? `playbook:${path}` : null;
  const stored = useQuery<Playbook>(key, () => api.playbook(path), { staleMs: 300_000 });

  const pb = stored.data;
  const data = pb?.data;
  const llmAvailable = pb?.llm_available ?? false;
  const newPrompts = pb?.new_prompts ?? 0;
  // Prompts can change without the count rising — reclassifying can remove
  // rows a playbook was written about — so staleness, not just growth, offers
  // the refresh.
  const outdated = Boolean(pb?.stale) || newPrompts > 0;

  async function run() {
    setWorking(true);
    setError(null);
    try {
      const fresh = await api.generatePlaybook(path, Boolean(data));
      // Reseed the cache so the panel shows the new playbook immediately.
      if (key) primeCache(key, { ...fresh, exists: true, llm_available: true, new_prompts: 0 });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="card mt-2 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-medium">
            {data
              ? "Your prompts, rewritten"
              : `Turn these ${recommendations.length} habits into a playbook`}
          </h3>
          <p className="mt-0.5 text-2xs text-content-subtle">
            {data
              ? newPrompts > 0
                ? `${newPrompts} new prompt${newPrompts === 1 ? "" : "s"} since this was written.`
                : outdated
                  ? "Your prompts have changed since this was written."
                  : "Up to date with your latest prompts."
              : "Rewrites your own low-scoring prompts to fix all of them at once."}
            {!llmAvailable && " Requires ANTHROPIC_API_KEY."}
          </p>
        </div>

        {/* Before anything exists: generate. Afterwards, only offer Refresh once
            new prompts have actually landed — otherwise it would re-buy the
            same advice. */}
        {(!data || outdated) && (
          <button
            onClick={run}
            disabled={working || !llmAvailable}
            title={
              llmAvailable
                ? undefined
                : "Set ANTHROPIC_API_KEY in .env and restart the backend"
            }
            className={`inline-flex h-11 shrink-0 items-center gap-1.5 rounded-md px-4 text-sm
                        font-medium transition-colors duration-200 ease-expo
                        disabled:cursor-not-allowed disabled:opacity-40 ${
                          data
                            ? "border border-line-strong text-content-muted hover:bg-surface-hover hover:text-content"
                            : "bg-accent text-canvas hover:bg-accent-hover"
                        }`}
          >
            {data ? (
              <RefreshIcon width={14} height={14} className={working ? "animate-spin" : ""} />
            ) : (
              <SparkIcon width={14} height={14} className={working ? "animate-spin" : ""} />
            )}
            {working ? "Working…" : data ? "Refresh" : "Generate playbook"}
          </button>
        )}
      </div>

      {working && (
        <div className="mt-4 space-y-2">
          <Skeleton className="h-3 w-1/3" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
        </div>
      )}

      {error && !working && (
        <p className="mt-3 text-sm text-score-low">
          {/5\d\d|auth|api_key/i.test(error)
            ? "Couldn't reach the Claude API. Check ANTHROPIC_API_KEY in .env, then restart the backend."
            : error}
        </p>
      )}

      {data && !working && (
        <div className="mt-4 space-y-4 border-t border-line pt-4">
          <p className="text-[13px] leading-relaxed text-content">{data.pattern}</p>

          <ul className="space-y-2">
            {data.rewrites.map((r, i) => (
              <RewriteCard key={r.prompt_id ?? `${r.label}-${i}`} rewrite={r} />
            ))}
          </ul>

          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <h4 className="eyebrow">A template you can reuse</h4>
              <CopyButton text={data.template} />
            </div>
            <pre
              className="overflow-x-auto whitespace-pre-wrap rounded-md border border-line-strong
                         bg-[#1B2436] p-4 font-mono text-[13px] leading-[1.75] text-[#E8EDF5]"
            >
              {data.template}
            </pre>
          </div>

          <div>
            <h4 className="eyebrow mb-2">What to do tomorrow</h4>
            <ol className="space-y-1.5">
              {data.habits.map((h, i) => (
                <li key={h} className="flex gap-2.5 text-[13px] leading-relaxed text-content-muted">
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center
                                   rounded-full bg-surface-overlay text-[10px] font-semibold
                                   tabular-nums text-content-muted">
                    {i + 1}
                  </span>
                  {h}
                </li>
              ))}
            </ol>
          </div>

          <p className="border-t border-line pt-2.5 text-2xs text-content-faint">
            Written by Claude from your measured weaknesses. Scores, percentages and
            signals are computed locally — the model only writes the prose and rewrites.
          </p>
        </div>
      )}
    </div>
  );
}
