import { scoreBarClass } from "./ScoreBadge";

/**
 * Factor-by-factor bars for a rubric score.
 *
 * Ordered by the rubric's own weights (clarity carries 25%, examples 10%) so
 * the factor that moves the overall score most is read first. Bars grow from
 * the left on mount; the animation is purely spatial and disabled under
 * prefers-reduced-motion by the global stylesheet.
 */
const FACTORS: { key: string; weight: number; hint: string }[] = [
  { key: "clarity", weight: 0.25, hint: "One clear ask, active voice, no hedging" },
  { key: "specificity", weight: 0.2, hint: "Names files, identifiers and output shape" },
  { key: "context", weight: 0.2, hint: "Background, intent and stack" },
  { key: "constraints", weight: 0.15, hint: "What not to do, and where to stop" },
  { key: "scope", weight: 0.1, hint: "One task, right size" },
  { key: "examples", weight: 0.1, hint: "Code, before/after or a worked case" },
];

export default function ScoreBreakdown({
  factors,
  highlight,
}: {
  factors: Record<string, number | null>;
  /** Factor to call out as the biggest opportunity. */
  highlight?: string | null;
}) {
  return (
    <ul className="space-y-2.5">
      {FACTORS.map(({ key, weight, hint }, i) => {
        const value = factors[key] ?? null;
        const pct = value === null ? 0 : (value / 10) * 100;
        const isWeak = highlight === key;

        return (
          <li key={key} className="group flex items-center gap-3" title={hint}>
            <div className="flex w-32 shrink-0 items-baseline gap-1.5">
              <span
                className={`text-sm capitalize ${
                  isWeak ? "font-medium text-content" : "text-content-muted"
                }`}
              >
                {key}
              </span>
              <span className="text-2xs text-content-faint tabular-nums">
                {Math.round(weight * 100)}%
              </span>
            </div>

            <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-overlay">
              <div
                className={`h-full origin-left rounded-full animate-bar-grow ${scoreBarClass(value)}`}
                style={{ width: `${pct}%`, animationDelay: `${i * 45}ms` }}
              />
            </div>

            <span className="w-9 shrink-0 text-right text-sm tabular-nums text-content-muted">
              {value === null ? "—" : value.toFixed(1)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
