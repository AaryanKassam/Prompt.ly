"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useQuery } from "@/lib/useQuery";
import ScoreBadge from "@/components/ScoreBadge";
import { CardListSkeleton, EmptyState, ErrorState } from "@/components/states";
import { ChevronRightIcon, FolderIcon } from "@/components/icons";

export default function ProjectsPage() {
  const projects = useQuery("projects", api.projects, { staleMs: 60_000 });
  const workspace = useQuery("workspace", api.activeWorkspace, { staleMs: 120_000 });
  const wsPath = workspace.data?.detected ? workspace.data.path : undefined;

  return (
    <div className="animate-fade-up space-y-6">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Projects</h1>
        <p className="mt-1 text-sm text-content-muted">
          Every folder Prompt.ly has recorded prompts for, busiest first.
        </p>
      </header>

      {projects.isLoading ? (
        <CardListSkeleton rows={5} />
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
                <div className="hidden text-right sm:block">
                  <div className="text-2xs text-content-subtle">
                    {p.prompt_count} prompts
                  </div>
                  <div className="text-2xs text-content-faint">
                    {p.session_count} session{p.session_count === 1 ? "" : "s"}
                  </div>
                </div>
                <ScoreBadge score={p.avg_score} size="sm" />
                <ChevronRightIcon
                  width={15}
                  height={15}
                  className="text-content-faint transition-transform duration-200 ease-expo
                             group-hover:translate-x-0.5 group-hover:text-content-muted"
                />
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No projects tracked yet"
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
    </div>
  );
}
