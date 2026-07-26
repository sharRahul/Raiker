export interface ContextUsageDisplay {
  label: string;
  percent: number;
}

function compactTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}K`;
  return String(tokens);
}

export function formatContextUsage(usedTokens: number, totalTokens: number): ContextUsageDisplay {
  const used = Math.max(0, Math.round(usedTokens));
  const total = Math.max(1, Math.round(totalTokens));
  const percent = Math.min(100, Math.round((used / total) * 100));
  return { label: `${compactTokens(used)} / ${compactTokens(total)} (${percent}%)`, percent };
}

/**
 * A decimal-string amount as currency.
 *
 * The server sends amounts as strings so a decimal price survives the round
 * trip without binary float drift; parsing happens once, here. `null` in means
 * `null` out — an amount Raiker cannot source must never be rendered as
 * "$0.00", which a reader would take to mean "this was free".
 *
 * API costs are routinely fractions of a cent, so the usual two decimal places
 * would collapse a real charge to $0.00 — or round $0.0143 to $0.01 and lose
 * most of it. Amounts below a whole unit get four decimals; at a unit and above,
 * two is what people expect to read.
 */
export function formatCost(
  amount: string | null | undefined,
  currency: string | null | undefined,
  locale?: string,
): string | null {
  if (amount === null || amount === undefined || amount === "") return null;
  const value = Number(amount);
  if (!Number.isFinite(value) || value < 0) return null;
  const digits = value > 0 && value < 1 ? 4 : 2;
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: currency || "USD",
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(value);
  } catch {
    // An unknown currency code must not break the popover.
    return `${value.toFixed(digits)} ${currency || ""}`.trim();
  }
}

/**
 * Human phrasing for where a number came from. The popover always shows this:
 * a pulled price and a shipped list price are different kinds of claim, and the
 * reader is entitled to know which one they are looking at.
 */
export function sourceNote(source: string | null | undefined, asOf?: string | null): string | null {
  switch (source) {
    case "provider":
      return "provider-reported";
    case "owner":
      return "your configured price";
    case "config":
      return asOf ? `list price, as of ${asOf}` : "list price";
    default:
      return null;
  }
}

/**
 * Each provider's share of total spend, as whole percents.
 *
 * Used for the Models page bars. A share is only meaningful against a non-zero
 * total, so an all-zero (or empty) input yields no shares at all rather than a
 * row of 0% bars or a divide-by-zero.
 */
export function spendShares(
  costs: { id: string; cost: string | null | undefined }[],
): Record<string, number> {
  const amounts = new Map<string, number>();
  let total = 0;
  for (const entry of costs) {
    const value = Number(entry.cost);
    if (entry.cost === null || entry.cost === undefined || !Number.isFinite(value) || value <= 0) {
      continue;
    }
    amounts.set(entry.id, value);
    total += value;
  }
  if (total <= 0) return {};
  const shares: Record<string, number> = {};
  for (const [id, value] of amounts) {
    shares[id] = Math.min(100, Math.round((value / total) * 100));
  }
  return shares;
}
