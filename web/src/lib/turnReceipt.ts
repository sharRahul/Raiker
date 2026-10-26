/**
 * QUI-F16 — a turn's receipt in one line, and in parts for its expanded view.
 *
 * "Claude Haiku 4.5 · ≈ $0.0143 · 2 files read · 1 change (approved 10:41) ·
 * nothing else left this computer". Every part comes from the receipt the
 * runtime built from the turn's audit events; this only words it.
 */
import type { TaskReceipt, TurnReceipt } from "./generated/apiContract";
import { formatCost } from "./contextPresentation";
import { localTime, providerName } from "./format";
import { modelName } from "./modelPresentation";

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function at(iso: string): string {
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime()) ? iso : localTime(parsed, { hour: "2-digit", minute: "2-digit" });
}

export function receiptParts(receipt: TurnReceipt): string[] {
  const parts: string[] = [];
  if (receipt.model) parts.push(modelName(receipt.model));
  if (receipt.cost_basis === "priced" && receipt.cost_usd !== null) {
    parts.push(`≈ ${formatCost(String(receipt.cost_usd), "USD") ?? `$${receipt.cost_usd}`}`);
  } else if (receipt.cost_basis === "free") {
    parts.push("no charge");
  } else {
    parts.push("cost not known");
  }
  const reads = Object.entries(receipt.reads).map(([noun, count]) => `${plural(count, noun)} read`);
  parts.push(...reads);
  if (receipt.changes.length > 0) {
    const approved = receipt.changes.filter((change) => change.approved_at !== null);
    const last = approved.at(-1)?.approved_at;
    const label = receipt.changes.length === 1 ? receipt.changes[0].label : plural(receipt.changes.length, "change");
    parts.push(last ? `${label} (approved ${at(last)})` : label);
  }
  if (receipt.left_computer.length > 0) {
    parts.push(`also reached ${receipt.left_computer.join(", ")}`);
  } else {
    parts.push(receipt.local ? "nothing left this computer" : "nothing else left this computer");
  }
  return parts;
}

export function receiptLine(receipt: TurnReceipt): string {
  return receiptParts(receipt).join(" · ");
}

/** The expanded rows: what each part means, in a sentence. */
export function receiptRows(receipt: TurnReceipt): { label: string; value: string }[] {
  const rows: { label: string; value: string }[] = [];
  const provider = receipt.provider ? ` (${providerName(receipt.provider)})` : "";
  rows.push({ label: "Model", value: receipt.model ? `${modelName(receipt.model)}${provider}` : "Not recorded" });
  rows.push({
    label: "Cost",
    value:
      receipt.cost_basis === "priced" && receipt.cost_usd !== null
        ? `About ${formatCost(String(receipt.cost_usd), "USD")}, from the tokens the provider reported`
        : receipt.cost_basis === "free"
          ? "No charge: this model is not billed per token"
          : "Not known: Raiker has no price for this model",
  });
  const reads = Object.entries(receipt.reads).map(([noun, count]) => plural(count, noun));
  rows.push({ label: "Read", value: reads.length > 0 ? reads.join(", ") : "Nothing" });
  rows.push({
    label: "Changed or sent",
    value:
      receipt.changes.length > 0
        ? receipt.changes
            .map((change) => (change.approved_at ? `${change.label}, approved ${at(change.approved_at)}` : `${change.label}, needed no approval`))
            .join("; ")
        : "Nothing",
  });
  rows.push({
    label: "Left this computer",
    value: receipt.local
      ? receipt.left_computer.length > 0
        ? receipt.left_computer.join(", ")
        : "Nothing"
      : [`The conversation, to ${receipt.provider ? providerName(receipt.provider) : "the model's provider"}`, ...receipt.left_computer].join("; "),
  });
  return rows;
}

/** A task's receipt in the shape of one turn's, so both read the same way. */
function asTurn(receipt: TaskReceipt): TurnReceipt {
  return {
    turn_id: receipt.task_id,
    model: receipt.models[0] ?? null,
    provider: null,
    local: receipt.local,
    cost_usd: receipt.cost_usd,
    cost_basis: receipt.cost_basis,
    reads: receipt.reads,
    changes: receipt.changes,
    left_computer: receipt.left_computer,
  };
}

/** QUI-F16 for a task: "Across 3 turns · Claude Haiku 4.5 · ≈ $0.03 · …". */
export function taskReceiptLine(receipt: TaskReceipt): string {
  if (receipt.turns === 0) return "Nothing has run yet.";
  const parts = receiptParts(asTurn(receipt));
  if (receipt.models.length > 1) parts[0] = receipt.models.map(modelName).join(" + ");
  return [`Across ${plural(receipt.turns, "turn")}`, ...parts].join(" · ");
}

export function taskReceiptRows(receipt: TaskReceipt): { label: string; value: string }[] {
  const rows = receiptRows(asTurn(receipt));
  if (receipt.models.length > 1) rows[0] = { label: "Models", value: receipt.models.map(modelName).join(", ") };
  return rows;
}
