"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Minimal stale-while-revalidate cache.
 *
 * Navigating back to a page you've already visited should be instant, not a
 * second of spinner — so results live in a module-level store keyed by string,
 * are served immediately on revisit, and refresh in the background. In-flight
 * requests are deduplicated so two components asking for the same key produce
 * one fetch.
 *
 * Deliberately ~60 lines instead of a TanStack Query dependency: the dashboard
 * has four read endpoints and one mutation.
 */

type Entry<T> = { data: T; at: number };

const cache = new Map<string, Entry<unknown>>();
const inflight = new Map<string, Promise<unknown>>();
const subscribers = new Map<string, Set<() => void>>();

const DEFAULT_STALE_MS = 30_000;

function notify(key: string) {
  subscribers.get(key)?.forEach((fn) => fn());
}

export function primeCache<T>(key: string, data: T) {
  cache.set(key, { data, at: Date.now() });
  notify(key);
}

export function invalidate(keyPrefix: string) {
  for (const key of Array.from(cache.keys())) {
    if (key.startsWith(keyPrefix)) cache.delete(key);
  }
}

async function load<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const existing = inflight.get(key);
  if (existing) return existing as Promise<T>;

  const promise = fetcher()
    .then((data) => {
      cache.set(key, { data, at: Date.now() });
      notify(key);
      return data;
    })
    .finally(() => {
      inflight.delete(key);
    });

  inflight.set(key, promise);
  return promise;
}

export interface QueryResult<T> {
  data: T | null;
  error: Error | null;
  /** True only on the very first load, when there's nothing to show yet. */
  isLoading: boolean;
  /** True while refreshing in the background with stale data on screen. */
  isValidating: boolean;
  refetch: (force?: boolean) => Promise<void>;
}

export function useQuery<T>(
  key: string | null,
  fetcher: () => Promise<T>,
  opts: { staleMs?: number } = {},
): QueryResult<T> {
  const staleMs = opts.staleMs ?? DEFAULT_STALE_MS;
  const cached = key ? (cache.get(key) as Entry<T> | undefined) : undefined;

  const [data, setData] = useState<T | null>(cached?.data ?? null);
  const [error, setError] = useState<Error | null>(null);
  const [isValidating, setValidating] = useState(false);

  // Keep the latest fetcher without making it a re-render trigger.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const run = useCallback(
    async (force = false) => {
      if (!key) return;
      const entry = cache.get(key) as Entry<T> | undefined;
      const fresh = entry && Date.now() - entry.at < staleMs;
      if (entry) setData(entry.data);
      if (fresh && !force) return;

      setValidating(true);
      try {
        setData(await load(key, fetcherRef.current));
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e : new Error(String(e)));
      } finally {
        setValidating(false);
      }
    },
    [key, staleMs],
  );

  useEffect(() => {
    if (!key) return;
    // Re-render this component whenever another one updates the same key.
    const onChange = () => setData((cache.get(key) as Entry<T>)?.data ?? null);
    const set = subscribers.get(key) ?? new Set();
    set.add(onChange);
    subscribers.set(key, set);

    void run();

    return () => {
      set.delete(onChange);
      if (set.size === 0) subscribers.delete(key);
    };
  }, [key, run]);

  return {
    data,
    error,
    // A null key means "nothing to fetch yet" — that is idle, not loading, or
    // callers gated on this would render a skeleton forever.
    isLoading: key !== null && data === null && error === null,
    isValidating,
    refetch: run,
  };
}
