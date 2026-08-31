"use client";

import { useState } from "react";
import Link from "next/link";
import { api, FactorEvidence } from "@/lib/api";
import { useQuery } from "@/lib/useQuery";
import { scoreBarClass } from "./ScoreBadge";
import { Skeleton } from "./states";
import { CheckIcon, ChevronRightIcon } from "./icons";

/**
 * Factor bars that expand into the evidence behind them.
 *
 * A bare "context 2.9/10" is a verdict with no appeal. Expanding shows which of
 * the last ten prompts passed or failed each signal in that factor, so the
 * number is traceable to specific things the user wrote.
 */
const FACTORS: { key: string; weight: number }[] = [
  { key: "clarity", weight: 0.22 },
  { key: "specificity", weight: 0.18 },
  { key: "context", weight: 0.17 },
  { key: "efficiency", weight: 0.15 },
  { key: "constraints", weight: 0.13 },
  { key: "scope", weight: 0.09 },
  { key: "examples", weight: 0.06 },
];

function Evidence({ factor, path }: { factor: string; path?: string }) {
  const { data, isLoading, error } = useQuery<FactorEvidence>(
    `factor:${path ?? "auto"}:${factor}`,
    () => api.factor(factor, path),
    { staleMs: 120_000 },
  );

  if (isLoading) {
    return (
      <div className="space-y-2 py-2">
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-3/4" />
      </div>
    );
  }
  if (error) return <p className="py-2 text-sm text-score-low">{error.message}</p>;
  if (!data) return null;

  return (
    <div className="space-y-3 py-1">
      <div>
        <div className="eyebrow mb-1.5">
          Across the last {data.window} prompt{data.window === 1 ? "" : "s"}
        </div>
        <ul className="space-y-1">
          {data.breakdown.map((b) => {
            const pct = b.total ? (b.met / b.total) * 100 : 0;
            return (
              <li key={b.name} className="flex items-center gap-2.5 text-2xs">
                <span className="w-11 shrink-0 text-right tabular-nums text-content-muted">
                  {b.met}/{b.total}
                </span>
                <span className="h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-surface-overlay">
                  <span
                    className={`block h-full rounded-full ${scoreBarClass((b.met / (b.total || 1)) * 10)}`}
                    style={{ width: `${pct}%` }}
                  />
                </span>
                <span className="text-content-muted">{b.label}</span>
              </li>
            );
          })}
        </ul>
      </div>

      <div>
        <div className="eyebrow mb-1.5">Prompt by prompt</div>
        <ul className="space-y-1">
          {data.prompts.map((p) => (
            <li key={p.id}>
              <Link
                href={`/prompts/${p.id}`}
                className="group flex items-start gap-2.5 rounded px-1 py-1
                           transition-colors duration-200 ease-expo hover:bg-surface-raised"
              >
                <span
                  className={`w-6 shrink-0 text-right text-2xs font-semibold tabular-nums ${
                    p.met === p.total
                      ? "text-score-high"
                      : p.met === 0
                        ? "text-score-low"
                        : "text-score-mid"
                  }`}
                >
                  {p.met}/{p.total}
                </span>
                <span className="flex shrink-0 gap-0.5 pt-0.5">
                  {p.signals.map((s) => (
                    <span
                      key={s.name}
                      title={`${s.met ? "met" : "missed"}: ${s.label}`}
                      className={`h-1.5 w-1.5 rounded-full ${
                        s.met ? "bg-score-high" : "bg-line-strong"
                      }`}
                    />
                  ))}
                </span>
                <span className="min-w-0 flex-1 truncate text-2xs text-content-muted">
                  {p.preview}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default function ExpandableFactors({
  factors,
  highlight,
  path,
}: {
  factors: Record<string, number | null>;
  highlight?: string | null;
  path?: string;
}) {
  const [open, setOpen] = useState<string | null>(null);

  return (
    <ul className="divide-y divide-line">
      {FACTORS.map(({ key, weight }) => {
        const value = factors[key] ?? null;
        const pct = value === null ? 0 : (value / 10) * 100;
        const isOpen = open === key;

        return (
          <li key={key} className="py-1.5 first:pt-0 last:pb-0">
            <button
              onClick={() => setOpen(isOpen ? null : key)}
              aria-expanded={isOpen}
              className="flex w-full items-center gap-3 rounded py-1 text-left
                         transition-colors duration-200 ease-expo hover:bg-surface-raised"
            >
              <ChevronRightIcon
                width={13}
                height={13}
                className={`shrink-0 text-content-faint transition-transform duration-200
                            ease-expo ${isOpen ? "rotate-90" : ""}`}
              />
              <span className="flex w-28 shrink-0 items-baseline gap-1.5">
                <span
                  className={`text-sm capitalize ${
                    highlight === key ? "font-medium text-content" : "text-content-muted"
                  }`}
                >
                  {key}
                </span>
                <span className="text-2xs tabular-nums text-content-faint">
                  {Math.round(weight * 100)}%
                </span>
              </span>
              <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface-overlay">
                <span
                  className={`block h-full rounded-full ${scoreBarClass(value)}`}
                  style={{ width: `${pct}%` }}
                />
              </span>
              <span className="w-9 shrink-0 text-right text-sm tabular-nums text-content-muted">
                {value === null ? "—" : value.toFixed(1)}
              </span>
            </button>

            {isOpen && (
              <div className="pl-6 pr-1">
                <Evidence factor={key} path={path} />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
