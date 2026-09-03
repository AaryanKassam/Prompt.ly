/**
 * Compact number formatting for stat tiles ("1.2k", "156.6M").
 *
 * The unit is chosen from the value *after* rounding, not before. Picking it
 * first means 999,999 formats as "1000.0k" — four digits in a slot sized for
 * three, and a unit the reader has to re-parse. The 999,950 threshold is where
 * `(n / 1e3).toFixed(1)` starts rounding up to "1000.0".
 */
export function compact(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 999_950) return `${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}
