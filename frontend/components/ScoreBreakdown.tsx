// Factor-by-factor bar chart for a prompt's rubric score.
const FACTOR_ORDER = [
  "clarity",
  "specificity",
  "context",
  "constraints",
  "scope",
  "examples",
];

function barColor(v: number): string {
  if (v < 5) return "bg-red-500";
  if (v < 7) return "bg-amber-500";
  return "bg-emerald-500";
}

export default function ScoreBreakdown({
  factors,
}: {
  factors: Record<string, number>;
}) {
  return (
    <div className="space-y-2">
      {FACTOR_ORDER.map((name) => {
        const v = factors[name] ?? 0;
        return (
          <div key={name} className="flex items-center gap-3">
            <div className="w-24 text-sm capitalize text-neutral-400">{name}</div>
            <div className="flex-1 h-2.5 rounded-full bg-neutral-800 overflow-hidden">
              <div
                className={`h-full rounded-full ${barColor(v)}`}
                style={{ width: `${(v / 10) * 100}%` }}
              />
            </div>
            <div className="w-10 text-right text-sm tabular-nums text-neutral-300">
              {v.toFixed(1)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
