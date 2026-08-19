import Link from "next/link";
import { AlertIcon, InboxIcon } from "./icons";

/** Grey block that reserves the exact space its real content will occupy. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

/** Row skeleton matching the shape of a session/project card. */
export function CardSkeleton() {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-3 w-1/3" />
        </div>
        <Skeleton className="h-7 w-12 shrink-0" />
      </div>
    </div>
  );
}

export function CardListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}

export function StatRowSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-busy="true">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="card p-4 space-y-2">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-7 w-20" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: React.ReactNode;
  action?: { href: string; label: string };
}) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-12 text-center">
      <div className="rounded-full bg-surface-overlay p-3 text-content-subtle">
        <InboxIcon width={22} height={22} />
      </div>
      <div>
        <h3 className="font-medium">{title}</h3>
        <p className="mx-auto mt-1 max-w-md text-sm text-content-muted">
          {description}
        </p>
      </div>
      {action && (
        <Link
          href={action.href}
          className="mt-1 rounded-md bg-accent px-3 py-2 text-sm font-medium text-canvas
                     transition-colors duration-200 ease-expo hover:bg-accent-hover"
        >
          {action.label}
        </Link>
      )}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: Error;
  onRetry?: () => void;
}) {
  const offline = /failed to fetch|networkerror|load failed/i.test(error.message);
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-10 text-center">
      <div className="rounded-full bg-score-low/10 p-3 text-score-low">
        <AlertIcon width={22} height={22} />
      </div>
      <div>
        <h3 className="font-medium">
          {offline ? "Can't reach the Prompt.ly API" : "Something went wrong"}
        </h3>
        <p className="mx-auto mt-1 max-w-md text-sm text-content-muted">
          {offline ? (
            <>
              Start the backend with{" "}
              <code className="rounded bg-surface-overlay px-1.5 py-0.5 font-mono text-2xs text-accent">
                uvicorn backend.main:app --port 8000
              </code>{" "}
              from the repo root.
            </>
          ) : (
            error.message
          )}
        </p>
      </div>
      {onRetry && (
        <button
          onClick={() => onRetry()}
          className="mt-1 rounded-md border border-line-strong px-3 py-2 text-sm font-medium
                     transition-colors duration-200 ease-expo hover:bg-surface-hover"
        >
          Try again
        </button>
      )}
    </div>
  );
}
