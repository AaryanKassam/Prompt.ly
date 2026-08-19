"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useQuery } from "@/lib/useQuery";
import ScoreBadge from "@/components/ScoreBadge";
import { CardListSkeleton, EmptyState, ErrorState } from "@/components/states";
import { ChevronRightIcon, FileIcon, TerminalIcon } from "@/components/icons";

export default function SessionsPage() {
  const sessions = useQuery("sessions", api.sessions, { staleMs: 60_000 });

  return (
    <div className="animate-fade-up space-y-6">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Sessions</h1>
          <p className="mt-1 text-sm text-content-muted">
            Every conversation, newest first.
          </p>
        </div>
        {sessions.data && (
          <span className="shrink-0 text-2xs text-content-subtle">
            {sessions.data.length} tracked
          </span>
        )}
      </header>

      {sessions.isLoading ? (
        <CardListSkeleton rows={5} />
      ) : sessions.error ? (
        <ErrorState error={sessions.error} onRetry={() => sessions.refetch(true)} />
      ) : sessions.data?.length ? (
        <div className="space-y-2">
          {sessions.data.map((s) => (
            <Link
              key={s.id}
              href={`/sessions/${s.id}`}
              className="card-interactive group flex items-center justify-between gap-4 p-4"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="rounded-md bg-surface-overlay p-2 text-content-subtle">
                  {s.source === "browser" ? (
                    <FileIcon width={15} height={15} />
                  ) : (
                    <TerminalIcon width={15} height={15} />
                  )}
                </span>
                <div className="min-w-0">
                  <div className="truncate font-medium">{s.title}</div>
                  <div className="mt-0.5 flex flex-wrap gap-2 text-2xs text-content-subtle">
                    <span>{s.prompt_count} prompts</span>
                    {s.created_at && (
                      <span>{new Date(s.created_at).toLocaleDateString()}</span>
                    )}
                    {s.project_path && (
                      <span className="truncate font-mono text-content-faint">
                        {s.project_path.split("/").slice(-1)[0]}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <ScoreBadge score={s.avg_score} size="sm" />
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
          title="No sessions yet"
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
