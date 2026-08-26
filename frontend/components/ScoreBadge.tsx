// Colored 0-10 score pill: red (<5) -> amber (<7) -> green.
export function scoreColor(score: number | null): string {
  if (score === null) return "bg-neutral-700 text-neutral-300";
  if (score < 5) return "bg-red-500/20 text-red-300 ring-1 ring-red-500/40";
  if (score < 7) return "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40";
  return "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40";
}

export default function ScoreBadge({ score }: { score: number | null }) {
  return (
    <span
      className={`inline-flex items-center justify-center rounded-md px-2 py-0.5 text-sm font-semibold tabular-nums ${scoreColor(
        score,
      )}`}
    >
      {score === null ? "—" : score.toFixed(1)}
    </span>
  );
}
