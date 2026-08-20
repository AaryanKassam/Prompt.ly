"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { invalidate, primeCache, useQuery } from "@/lib/useQuery";
import ScoreBadge from "@/components/ScoreBadge";
import ExpandableFactors from "@/components/ExpandableFactors";
import ImprovePanel from "@/components/ImprovePanel";
import ExecutePanel from "@/components/ExecutePanel";
import Tooltip from "@/components/Tooltip";
import { StatTile, TrendPill } from "@/components/StatTile";
import { CardListSkeleton, EmptyState, ErrorState, StatRowSkeleton } from "@/components/states";
import { ArrowLeftIcon, FileIcon, RefreshIcon, TerminalIcon } from "@/components/icons";

function compact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function ReportView() {
  const params = useSearchParams();
  const path = params.get("path") ?? undefined;
  const [refreshing, setRefreshing] = useState(false);

  const key = path ? `report:${path}` : "report:auto";
  const report = useQuery(key, () => api.report(path), { staleMs: 60_000 });

  async function refresh() {
    setRefreshing(true);
    try {
      // Re-imports session logs server-side, then reseeds the cache so every
      // view of this project updates at once.
      const fresh = await api.refreshReport(path);
      primeCache(key, fresh);
      invalidate("projects");
    } finally {
      setRefreshing(false);
    }
  }

  if (report.error) {
    return <ErrorState error={report.error} onRetry={() => report.refetch(true)} />;
  }

  const r = report.data;
  const name = (r?.project_path ?? path ?? "").split("/").filter(Boolean).pop();

  return (
    <div className="animate-fade-up space-y-6">
      <Link
        href="/projects"
        className="inline-flex items-center gap-1.5 text-sm text-content-subtle
                   transition-colors duration-200 ease-expo hover:text-content"
      >
        <ArrowLeftIcon width={15} height={15} />
        All projects
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">
            {name ?? "Prompt report"}
          </h1>
          <p className="mt-1 truncate font-mono text-2xs text-content-subtle">
            {r?.project_path ?? path ?? "auto-detecting…"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {r && (
            <span className="text-2xs text-content-subtle">
              {r.cached ? "cached" : "freshly computed"}
            </span>
          )}
          <Tooltip label="Re-import session logs and rebuild">
            <button
              onClick={refresh}
              disabled={refreshing}
              aria-label="Refresh report"
              className="inline-flex h-11 w-11 items-center justify-center rounded-md
                         border border-line text-content-muted transition-colors duration-200
                         ease-expo hover:bg-surface-hover hover:text-content
                         disabled:opacity-50"
            >
              <RefreshIcon
                width={16}
                height={16}
                className={refreshing ? "animate-spin" : ""}
              />
            </button>
          </Tooltip>
        </div>
      </header>

      {report.isLoading ? (
        <>
          <StatRowSkeleton />
          <CardListSkeleton rows={3} />
        </>
      ) : !r || r.totals.prompts === 0 ? (
        <EmptyState
          title="No prompts recorded for this folder"
          description={
            <>
              Use Claude Code here, then hit refresh — Prompt.ly reads the session
              logs already on your machine.
            </>
          }
          action={{ href: "/projects", label: "Back to projects" }}
        />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              label="Prompt score"
              value={
                <span className="flex items-baseline gap-2">
                  {r.overall?.toFixed(1) ?? "—"}
                  <span className="text-sm font-medium text-content-subtle">
                    {r.grade}
                  </span>
                </span>
              }
              footnote={
                r.trend ? (
                  <TrendPill direction={r.trend.direction} delta={r.trend.delta} />
                ) : (
                  `${r.totals.scored_prompts} scored`
                )
              }
              tone="accent"
            />
            <StatTile
              label="Prompts"
              value={r.totals.prompts}
              footnote={`${r.totals.sessions} session${r.totals.sessions === 1 ? "" : "s"}`}
            />
            <StatTile
              label="Files touched"
              value={r.totals.files_touched}
              footnote={`${r.totals.files_created} created · ${r.totals.files_edited} edited`}
            />
            <StatTile
              label="Output tokens"
              value={compact(r.totals.output_tokens)}
              footnote={`${r.totals.tool_calls} tool calls`}
            />
          </div>

          <section className="card p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="eyebrow">Factor breakdown · click to expand</h2>
              <div className="flex gap-3 text-2xs text-content-subtle">
                {r.strongest_factor && (
                  <span>
                    strongest:{" "}
                    <span className="capitalize text-score-high">
                      {r.strongest_factor}
                    </span>
                  </span>
                )}
                {r.weakest_factor && (
                  <span>
                    weakest:{" "}
                    <span className="capitalize text-score-mid">
                      {r.weakest_factor}
                    </span>
                  </span>
                )}
              </div>
            </div>
            <ExpandableFactors
              factors={r.factors}
              highlight={r.weakest_factor}
              path={r.project_path}
            />
          </section>

          {r.recommendations.length > 0 && (
            <section>
              <h2 className="eyebrow mb-3">Do these next</h2>
              <ol className="space-y-2">
                {r.recommendations.map((rec, i) => (
                  <li key={rec.signal} className="card flex gap-4 p-4">
                    <span
                      className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center
                                 rounded-full bg-surface-overlay text-2xs font-semibold
                                 tabular-nums text-content-muted"
                    >
                      {i + 1}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm leading-relaxed">{rec.advice}</p>
                      <div className="mt-1.5 flex items-center gap-2">
                        <span className="rounded bg-score-mid/10 px-1.5 py-0.5 text-2xs text-score-mid">
                          {rec.missed_pct}% of prompts miss this
                        </span>
                        <span className="text-2xs capitalize text-content-faint">
                          {rec.factor}
                        </span>
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
              <ExecutePanel
                recommendations={r.recommendations}
                path={r.project_path}
              />
            </section>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            {r.worst_prompts.length > 0 && (
              <section>
                <h2 className="eyebrow mb-3">Lowest-scoring prompts</h2>
                <div className="space-y-2">
                  {r.worst_prompts.map((p) => (
                    <ImprovePanel key={p.id} prompt={p} />
                  ))}
                </div>
              </section>
            )}

            {r.best_prompts.length > 0 && (
              <section>
                <h2 className="eyebrow mb-3">Best prompts</h2>
                <div className="space-y-2">
                  {r.best_prompts.map((p) => (
                    <Link
                      key={p.id}
                      href={`/prompts/${p.id}`}
                      className="card-interactive flex items-start gap-3 p-3.5"
                    >
                      <ScoreBadge score={p.score} size="sm" />
                      <p className="min-w-0 flex-1 text-sm leading-relaxed text-content-muted">
                        {p.preview}
                      </p>
                    </Link>
                  ))}
                </div>
              </section>
            )}
          </div>

          <section>
            <h2 className="eyebrow mb-3">Sessions in this project</h2>
            <div className="space-y-2">
              {r.sessions.map((s) => (
                <Link
                  key={s.id}
                  href={`/sessions/${s.id}`}
                  className="card-interactive flex items-center justify-between gap-4 p-3.5"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="rounded-md bg-surface-overlay p-1.5 text-content-subtle">
                      {s.source === "browser" ? (
                        <FileIcon width={14} height={14} />
                      ) : (
                        <TerminalIcon width={14} height={14} />
                      )}
                    </span>
                    <span className="truncate text-sm">{s.title}</span>
                  </div>
                  <span className="shrink-0 text-2xs text-content-subtle">
                    {s.prompt_count} prompts
                    {s.created_at &&
                      ` · ${new Date(s.created_at).toLocaleDateString()}`}
                  </span>
                </Link>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default function ProjectReportPage() {
  // useSearchParams needs a Suspense boundary in the App Router.
  return (
    <Suspense fallback={<StatRowSkeleton />}>
      <ReportView />
    </Suspense>
  );
}
