/**
 * The 0-10 score pill.
 *
 * One shared colour scale (red < 5 <= amber < 7 <= green) so a score reads the
 * same on a card, a table row and a report header. Colour never carries the
 * meaning alone — the number is always present too.
 */
export type ScoreTone = "low" | "mid" | "high" | "none";

export function scoreTone(score: number | null): ScoreTone {
  if (score === null || Number.isNaN(score)) return "none";
  if (score < 5) return "low";
  if (score < 7) return "mid";
  return "high";
}

const PILL: Record<ScoreTone, string> = {
  low: "bg-score-low/10 text-score-low ring-score-low/25",
  mid: "bg-score-mid/10 text-score-mid ring-score-mid/25",
  high: "bg-score-high/10 text-score-high ring-score-high/25",
  none: "bg-surface-overlay text-content-subtle ring-line-strong",
};

const BAR: Record<ScoreTone, string> = {
  low: "bg-score-low",
  mid: "bg-score-mid",
  high: "bg-score-high",
  none: "bg-content-faint",
};

export function scoreBarClass(score: number | null): string {
  return BAR[scoreTone(score)];
}

export default function ScoreBadge({
  score,
  size = "md",
}: {
  score: number | null;
  size?: "sm" | "md" | "lg";
}) {
  const sizing = {
    sm: "px-1.5 py-0.5 text-2xs",
    md: "px-2 py-1 text-sm",
    lg: "px-3 py-1.5 text-lg",
  }[size];

  return (
    <span
      className={`inline-flex items-center justify-center rounded-md font-semibold
                  tabular-nums ring-1 ${sizing} ${PILL[scoreTone(score)]}`}
      title={score === null ? "Not scored" : `${score.toFixed(2)} out of 10`}
    >
      {score === null ? "—" : score.toFixed(1)}
    </span>
  );
}
