import { TrendDownIcon, TrendFlatIcon, TrendUpIcon } from "./icons";

/**
 * Single KPI tile. Value dominates, label sits above it in the eyebrow style,
 * optional footnote sits below — the same three-slot shape for every metric so
 * a row of tiles scans as one unit.
 */
export function StatTile({
  label,
  value,
  footnote,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  footnote?: React.ReactNode;
  tone?: "default" | "accent";
}) {
  return (
    <div className="card p-4">
      <div className="eyebrow">{label}</div>
      <div
        className={`mt-1.5 text-2xl font-semibold tabular-nums tracking-tight ${
          tone === "accent" ? "text-accent" : "text-content"
        }`}
      >
        {value}
      </div>
      {footnote && (
        <div className="mt-1 text-2xs text-content-subtle">{footnote}</div>
      )}
    </div>
  );
}

const TREND_STYLE = {
  improving: { Icon: TrendUpIcon, cls: "text-score-high", verb: "improving" },
  declining: { Icon: TrendDownIcon, cls: "text-score-low", verb: "declining" },
  flat: { Icon: TrendFlatIcon, cls: "text-content-muted", verb: "holding steady" },
} as const;

export function TrendPill({
  direction,
  delta,
}: {
  direction: "improving" | "declining" | "flat";
  delta: number;
}) {
  const { Icon, cls, verb } = TREND_STYLE[direction];
  return (
    <span className={`inline-flex items-center gap-1.5 text-2xs ${cls}`}>
      <Icon width={13} height={13} />
      <span>
        {verb}
        {direction !== "flat" && (
          <span className="tabular-nums"> {delta > 0 ? "+" : ""}{delta.toFixed(2)}</span>
        )}
      </span>
    </span>
  );
}
