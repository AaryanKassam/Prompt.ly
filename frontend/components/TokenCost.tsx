import type { TokenEconomics } from "@/lib/api";
import { compact } from "@/lib/format";

/**
 * What this project's prompting actually cost, in tokens.
 *
 * Separate from the `efficiency` factor, which predicts cost from a prompt's
 * text. This is the measured spend, so the two can be read against each other.
 *
 * "Per file changed" is the headline rather than a raw total: raw token counts
 * punish a big task for being big, while cost per unit of work delivered is
 * comparable between a one-line fix and a refactor.
 */
const BAND_STYLE: Record<string, string> = {
  lean: "text-score-high",
  typical: "text-score-mid",
  heavy: "text-score-low",
  unknown: "text-content-subtle",
};

export default function TokenCost({ econ }: { econ: TokenEconomics }) {
  if (!econ || !econ.prompts_with_tokens) return null;

  return (
    <section className="card p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="eyebrow">Token cost</h2>
        <span className={`text-2xs capitalize ${BAND_STYLE[econ.cost_band]}`}>
          {econ.cost_band} spend
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <div className="text-xl font-semibold tabular-nums">
            {compact(econ.total_tokens)}
          </div>
          <div className="mt-0.5 text-2xs text-content-subtle">total tokens</div>
        </div>
        <div>
          <div className="text-xl font-semibold tabular-nums">
            {compact(econ.context_tokens)}
          </div>
          <div className="mt-0.5 text-2xs text-content-subtle">
            context, cache included
          </div>
        </div>
        <div>
          <div className="text-xl font-semibold tabular-nums">
            {compact(econ.median_output_per_prompt)}
          </div>
          <div className="mt-0.5 text-2xs text-content-subtle">
            median reply per prompt
          </div>
        </div>
        <div>
          <div className="text-xl font-semibold tabular-nums">
            {compact(econ.output_per_file_changed)}
          </div>
          <div className="mt-0.5 text-2xs text-content-subtle">
            per file changed
          </div>
        </div>
      </div>

      {econ.most_expensive.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <h3 className="eyebrow mb-2.5">Most expensive turns</h3>
          <ul className="space-y-2">
            {econ.most_expensive.map((p) => (
              <li key={p.id} className="flex items-start gap-3">
                <span className="w-14 shrink-0 text-right text-xs font-medium tabular-nums text-score-low">
                  {compact(p.output_tokens)}
                </span>
                <span className="min-w-0 flex-1 truncate text-xs text-content-subtle">
                  {p.preview}
                </span>
                {p.score !== null && (
                  <span className="shrink-0 text-2xs tabular-nums text-content-subtle">
                    {p.score.toFixed(1)}/10
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
