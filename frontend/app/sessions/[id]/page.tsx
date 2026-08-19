"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useQuery } from "@/lib/useQuery";
import ScoreBadge from "@/components/ScoreBadge";
import { CardListSkeleton, EmptyState, ErrorState, Skeleton } from "@/components/states";
import { ArrowLeftIcon } from "@/components/icons";

function diffLabel(d: { created: number; edited: number; deleted: number }) {
  const parts: string[] = [];
  if (d.created) parts.push(`+${d.created}`);
  if (d.edited) parts.push(`~${d.edited}`);
  if (d.deleted) parts.push(`-${d.deleted}`);
  return parts.join(" ");
}

export default function SessionPage({ params }: { params: { id: string } }) {
  const session = useQuery(`session:${params.id}`, () => api.session(params.id), {
    staleMs: 60_000,
  });

  if (session.error) {
    return <ErrorState error={session.error} onRetry={() => session.refetch(true)} />;
  }

  const data = session.data;

  return (
    <div className="animate-fade-up space-y-6">
      <Link
        href="/sessions"
        className="inline-flex items-center gap-1.5 text-sm text-content-subtle
                   transition-colors duration-200 ease-expo hover:text-content"
      >
        <ArrowLeftIcon width={15} height={15} />
        All sessions
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          {data ? (
            <>
              <h1 className="text-xl font-semibold tracking-tight">{data.title}</h1>
              {data.project_path && (
                <Link
                  href={`/projects/report?path=${encodeURIComponent(data.project_path)}`}
                  className="mt-1 inline-block truncate font-mono text-2xs text-content-subtle
                             transition-colors duration-200 ease-expo hover:text-accent"
                >
                  {data.project_path}
                </Link>
              )}
            </>
          ) : (
            <div className="space-y-2">
              <Skeleton className="h-6 w-64" />
              <Skeleton className="h-3 w-40" />
            </div>
          )}
        </div>
        {data && (
          <div className="flex shrink-0 items-center gap-2">
            <span className="eyebrow">session avg</span>
            <ScoreBadge score={data.avg_score} />
          </div>
        )}
      </header>

      {session.isLoading ? (
        <CardListSkeleton rows={5} />
      ) : !data?.prompts.length ? (
        <EmptyState
          title="No prompts in this session"
          description="The session was recorded but contains no user turns."
        />
      ) : (
        <ol className="space-y-2">
          {data.prompts.map((p) => (
            <li key={p.id}>
              <Link
                href={`/prompts/${p.id}`}
                className="card-interactive block p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="eyebrow mb-1.5">Turn {p.turn_index}</div>
                    <p className="line-clamp-2 text-sm leading-relaxed">
                      {p.text_preview || (
                        <span className="italic text-content-faint">
                          (no text captured)
                        </span>
                      )}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-3 text-2xs text-content-subtle">
                      {p.tool_count > 0 && <span>{p.tool_count} tool calls</span>}
                      {diffLabel(p.diffs) && (
                        <span className="font-mono">{diffLabel(p.diffs)} files</span>
                      )}
                      {p.output_tokens != null && (
                        <span>{p.output_tokens.toLocaleString()} out tokens</span>
                      )}
                    </div>
                  </div>
                  <ScoreBadge score={p.overall} size="sm" />
                </div>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
