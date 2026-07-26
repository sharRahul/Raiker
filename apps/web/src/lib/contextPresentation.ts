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
