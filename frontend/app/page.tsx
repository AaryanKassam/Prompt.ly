"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useQuery } from "@/lib/useQuery";
import ScoreBadge from "@/components/ScoreBadge";
import ScoreBreakdown from "@/components/ScoreBreakdown";
import { StatTile, TrendPill } from "@/components/StatTile";
import { CardListSkeleton, EmptyState, ErrorState, Skeleton, StatRowSkeleton } from "@/components/states";
import { ChevronRightIcon, FolderIcon } from "@/components/icons";

function compact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export default function OverviewPage() {
  const workspace = useQuery("workspace", api.activeWorkspace, { staleMs: 120_000 });
  const wsPath = workspace.data?.detected ? workspace.data.path : undefined;

  // The report for the folder you're actually sitting in — the same payload the
  // Claude extension serves, so both surfaces always agree.
  const report = useQuery(
    wsPath ? `report:${wsPath}` : null,
    () => api.report(wsPath),
    { staleMs: 60_000 },
  );
  const projects = useQuery("projects", api.projects, { staleMs: 60_000 });

  if (report.error && projects.error) {
    return <ErrorState error={report.error} onRetry={() => report.refetch(true)} />;
  }

  const r = report.data;
  const t = r?.totals;

  return (
    <div className="animate-fade-up space-y-7">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
        {/* A div, not a p: the loading skeleton is a block element. */}
        <div className="mt-1 text-sm text-content-muted">
          {workspace.data?.detected ? (
            <>
              Working in{" "}
              <span className="font-mono text-content">{wsPath}</span>
              <span className="text-content-subtle">
                {" "}· detected via {workspace.data.editor}
              </span>
            </>
          ) : workspace.isLoading ? (
            <Skeleton className="h-4 w-64" />
          ) : (
            "No editor workspace detected — pick a project below."
          )}
        </div>
      </header>

      {/* KPI row */}
      {report.isLoading || (!r && wsPath) ? (
        <StatRowSkeleton />
      ) : r && t && t.prompts > 0 ? (
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
                `across ${t.scored_prompts} prompts`
              )
            }
            tone="accent"
          />
          <StatTile
            label="Prompts"
            value={t.prompts}
            footnote={`${t.sessions} session${t.sessions === 1 ? "" : "s"}`}
          />
          <StatTile
            label="Files touched"
            value={t.files_touched}
            footnote={`${t.files_created} created · ${t.files_edited} edited`}
          />
          <StatTile
            label="Output tokens"
            value={compact(t.output_tokens)}
            footnote={`${t.tool_calls} tool calls`}
          />
        </div>
      ) : null}

      {/* Factors + top recommendation */}
      {r && t && t.prompts > 0 && (
        <div className="grid gap-4 lg:grid-cols-5">
          <section className="card p-5 lg:col-span-3">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="eyebrow">Factor breakdown</h2>
              {r.weakest_factor && (
                <span className="text-2xs text-content-subtle">
                  weakest:{" "}
                  <span className="capitalize text-score-mid">
                    {r.weakest_factor}
                  </span>
                </span>
              )}
            </div>
            <ScoreBreakdown factors={r.factors} highlight={r.weakest_factor} />
          </section>

          <section className="card p-5 lg:col-span-2">
            <h2 className="eyebrow mb-3">Biggest opportunity</h2>
            {r.recommendations.length > 0 ? (
              <div className="space-y-3">
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-semibold tabular-nums text-score-mid">
                    {r.recommendations[0].missed_pct}%
                  </span>
                  <span className="text-sm text-content-muted">
                    of prompts miss this
                  </span>
                </div>
                <p className="text-sm leading-relaxed text-content">
                  {r.recommendations[0].advice}
                </p>
                <Link
                  href={`/projects/report?path=${encodeURIComponent(wsPath!)}`}
                  className="inline-flex items-center gap-1 text-sm text-accent
                             transition-colors duration-200 ease-expo hover:text-accent-hover"
                >
                  See all {r.recommendations.length} recommendations
                  <ChevronRightIcon width={14} height={14} />
                </Link>
              </div>
            ) : (
              <p className="text-sm text-content-muted">
                Not enough scored prompts here yet.
              </p>
            )}
          </section>
        </div>
      )}

      {/* Empty state when the detected folder has no data */}
      {r && t && t.prompts === 0 && (
        <EmptyState
          title="No prompts recorded for this folder yet"
          description={
            <>
              Use Claude Code in{" "}
              <span className="font-mono text-content-muted">{wsPath}</span>, then
              run{" "}
              <code className="rounded bg-surface-overlay px-1.5 py-0.5 font-mono text-2xs text-accent">
                python scripts/import_jsonl.py
              </code>
              .
            </>
          }
          action={{ href: "/projects", label: "Browse tracked projects" }}
        />
      )}

      {/* All projects */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="eyebrow">All projects</h2>
          {projects.data && (
            <span className="text-2xs text-content-subtle">
              {projects.data.length} tracked
            </span>
          )}
        </div>

        {projects.isLoading ? (
          <CardListSkeleton rows={3} />
        ) : projects.error ? (
          <ErrorState error={projects.error} onRetry={() => projects.refetch(true)} />
        ) : projects.data?.length ? (
          <div className="space-y-2">
            {projects.data.map((p) => (
              <Link
                key={p.project_path}
                href={`/projects/report?path=${encodeURIComponent(p.project_path)}`}
                className="card-interactive group flex items-center justify-between gap-4 p-4"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span
                    className={`rounded-md p-2 ${
                      p.project_path === wsPath
                        ? "bg-accent-soft text-accent"
                        : "bg-surface-overlay text-content-subtle"
                    }`}
                  >
                    <FolderIcon width={15} height={15} />
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{p.name}</span>
                      {p.project_path === wsPath && (
                        <span className="rounded bg-accent-soft px-1.5 py-0.5 text-2xs text-accent">
                          open now
                        </span>
                      )}
                    </div>
                    <div className="truncate font-mono text-2xs text-content-subtle">
                      {p.project_path}
                    </div>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="hidden text-2xs text-content-subtle sm:inline">
                    {p.prompt_count} prompts
                  </span>
                  <ScoreBadge score={p.avg_score} size="sm" />
                  <ChevronRightIcon
                    width={15}
                    height={15}
                    className="text-content-faint transition-transform duration-200
                               ease-expo group-hover:translate-x-0.5 group-hover:text-content-muted"
                  />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Nothing tracked yet"
            description={
              <>
                Run{" "}
                <code className="rounded bg-surface-overlay px-1.5 py-0.5 font-mono text-2xs text-accent">
                  python scripts/import_jsonl.py
                </code>{" "}
                to import your Claude Code history.
              </>
            }
          />
        )}
      </section>
    </div>
  );
}
