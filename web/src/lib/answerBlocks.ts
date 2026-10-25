/**
 * Quiet UI 04 — the visual answer blocks, as text and as grids.
 *
 * The runtime validates every block (`raiker/runtime/typed_parts.py`) and this
 * never re-checks it; it only turns an accepted block into the two other forms
 * the block toolbar offers: the sentence form behind **Show as text** and
 * **Copy**, and the rows behind **Table** and **CSV**. The wording matches the
 * runtime's own `as_text`, so an export, an unsourced block and Show as text
 * all say the same thing.
 */
import type { ContentPart } from "./apiTypes";

export type BlockType =
  | "table"
  | "chart"
  | "figures"
  | "compare"
  | "measure"
  | "callout"
  | "proscons"
  | "steps";

export const BLOCK_TYPES: ReadonlySet<string> = new Set<BlockType>([
  "table",
  "chart",
  "figures",
  "compare",
  "measure",
  "callout",
  "proscons",
  "steps",
]);

export type Series = { name: string; values: number[] };
export type Figure = { label: string; value: number; unit: string; of: string; estimate: boolean };
export type CompareRow = {
  label: string;
  unit: string;
  better: "" | "higher" | "lower";
  values: (number | string)[];
  best: number[];
};
export type ProsConsOption = { name: string; pros: string[]; cons: string[] };
export type Step = { label: string; when: string; text: string };

/** Units written before the number, the way a price is read: £999, not 999 £. */
export const PREFIX_UNITS: ReadonlySet<string> = new Set(["£", "$", "€", "¥", "₹", "US$", "A$", "C$"]);

/** A number as a person writes it: no trailing `.0`, no float noise. */
export function figure(value: number, unit = ""): string {
  const text = Number.isInteger(value) ? String(value) : String(Number(value.toPrecision(6)));
  if (PREFIX_UNITS.has(unit)) return text.startsWith("-") ? `-${unit}${text.slice(1)}` : `${unit}${text}`;
  return unit ? `${text} ${unit}` : text;
}

const CALLOUT_LEADS: Record<string, string> = {
  verdict: "Verdict",
  warning: "Warning",
  action: "Next step",
};

export function calloutLead(tone: string): string {
  return CALLOUT_LEADS[tone] ?? "Verdict";
}

function data(part: ContentPart): Record<string, unknown> {
  return (part.data ?? {}) as Record<string, unknown>;
}

/** Every block's sentence form: what Show as text shows and Copy copies. */
export function blockText(part: ContentPart): string {
  const d = data(part);
  const caption = String(d.caption ?? "");
  const head = caption ? [`${caption}`, ""] : [];
  const estimate = d.estimate ? " (≈ estimate)" : "";
  switch (part.type) {
    case "figures":
      return [
        ...head,
        ...(d.items as Figure[]).map(
          (item) =>
            `- ${item.label}: ${figure(item.value, item.unit)}${item.of ? ` (${item.of})` : ""}${
              item.estimate || d.estimate ? " (≈ estimate)" : ""
            }`,
        ),
      ].join("\n");
    case "compare": {
      const items = d.items as string[];
      return [
        ...(caption ? [`${caption}${estimate}`, ""] : []),
        ...(d.rows as CompareRow[]).map(
          (row) =>
            `- ${row.label}: ` +
            row.values
              .map((value, index) => {
                const shown = typeof value === "number" ? figure(value, row.unit) : value;
                return `${items[index]} ${shown}${row.best.includes(index) ? " (best)" : ""}`;
              })
              .join("; "),
        ),
      ].join("\n");
    }
    case "measure": {
      const unit = String(d.unit ?? "");
      const min = Number(d.min ?? 0);
      const low = min === 0 ? "" : `${figure(min)}–`;
      return `${String(d.label)}: ${figure(Number(d.value), unit)} of ${low}${figure(Number(d.max), unit)}${estimate}`;
    }
    case "callout":
      return `${calloutLead(String(d.tone))}: ${String(d.text ?? "")}`;
    case "proscons":
      return [
        ...head,
        ...(d.options as ProsConsOption[]).flatMap((option) => [
          option.name,
          ...option.pros.map((entry) => `- Pro: ${entry}`),
          ...option.cons.map((entry) => `- Con: ${entry}`),
          "",
        ]),
      ]
        .join("\n")
        .trimEnd();
    case "steps":
      return [
        ...head,
        ...(d.steps as Step[]).map(
          (step, index) =>
            `${index + 1}. ${step.label}${step.when ? ` (${step.when})` : ""}${step.text ? ` — ${step.text}` : ""}`,
        ),
      ].join("\n");
    default: {
      const grid = blockGrid(part);
      if (grid === null) return part.text ?? "";
      return [...head, ...[grid.columns, ...grid.rows].map((row) => row.join("\t"))].join("\n");
    }
  }
}

export type Grid = { columns: string[]; rows: string[][] };

/**
 * The block as rows, for the ones that are grids of values: what Table shows
 * for a chart and what CSV downloads. `null` for prose blocks (a callout, pros
 * and cons, steps), which have no columns to put in a spreadsheet.
 */
export function blockGrid(part: ContentPart): Grid | null {
  const d = data(part);
  switch (part.type) {
    case "table":
      return { columns: d.columns as string[], rows: d.rows as string[][] };
    case "chart": {
      const series = d.series as Series[];
      const labels = d.labels as string[];
      return {
        columns: [String(d.y_label ?? "") || "Label", ...series.map((s, i) => s.name || `Series ${i + 1}`)],
        rows: labels.map((label, index) => [label, ...series.map((s) => figure(s.values[index]))]),
      };
    }
    case "figures":
      return {
        columns: ["Figure", "Value", "Unit", "Of", "Estimate"],
        rows: (d.items as Figure[]).map((item) => [
          item.label,
          figure(item.value),
          item.unit,
          item.of,
          item.estimate || d.estimate ? "yes" : "no",
        ]),
      };
    case "compare": {
      const items = d.items as string[];
      return {
        columns: ["", ...items],
        rows: (d.rows as CompareRow[]).map((row) => [
          row.unit ? `${row.label} (${row.unit})` : row.label,
          ...row.values.map((value, index) => {
            const shown = typeof value === "number" ? figure(value) : value;
            return row.best.includes(index) ? `${shown} (best)` : shown;
          }),
        ]),
      };
    }
    case "measure":
      return {
        columns: ["Measure", "Value", "Minimum", "Maximum", "Unit"],
        rows: [[String(d.label), figure(Number(d.value)), figure(Number(d.min ?? 0)), figure(Number(d.max)), String(d.unit ?? "")]],
      };
    default:
      return null;
  }
}

/** RFC 4180: a cell with a comma, quote or line break is quoted, quotes doubled. */
function csvCell(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export function toCsv(grid: Grid): string {
  return [grid.columns, ...grid.rows].map((row) => row.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

/** A download name from the caption, reduced to characters every OS accepts. */
export function blockFilename(part: ContentPart, extension: string): string {
  const caption = String(data(part).caption ?? data(part).label ?? "");
  const slug = caption.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase().slice(0, 60);
  return `${slug || `raiker-${part.type}`}.${extension}`;
}

/** How many drawn blocks an answer has. Refusals and prose are not counted. */
export function blockCount(parts: readonly ContentPart[]): number {
  return parts.filter((part) => BLOCK_TYPES.has(part.type)).length;
}

/** QUI-A rules: more than this, and the answer is offered as a document. */
export const BLOCKS_PER_ANSWER = 3;

const BLOCK_NAMES: Record<BlockType, string> = {
  table: "a table",
  chart: "a chart",
  figures: "key figures",
  compare: "a comparison",
  measure: "a measure",
  callout: "a callout",
  proscons: "pros and cons",
  steps: "the steps",
};

/**
 * Quiet UI 04 — what a streaming answer shows of its `raiker:` blocks.
 *
 * The typed parts arrive with the final response, so while a turn streams its
 * block was visible as raw JSON in a code sample and then replaced by the drawn
 * block at the end. While streaming, each `raiker:` fence — finished or still
 * open — is held back and replaced by one line naming what is being prepared.
 * The fence type is the model's own declaration, so the line says no more than
 * the answer already does. Prose either side is untouched.
 */
export function holdBackBlocks(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  let inBlock = false;
  for (const line of lines) {
    if (!inBlock) {
      const open = /^\s*(`{3,}|~{3,})\s*raiker:([a-z]+)/i.exec(line);
      if (open) {
        inBlock = true;
        const kind = open[2].toLowerCase() as BlockType;
        out.push(`*Preparing ${BLOCK_NAMES[kind] ?? "a block"}…*`);
        // A fence whose JSON closes on its own line closes the block too.
        if (/(`{3,}|~{3,})\s*$/.test(line.slice(open.index + open[0].length))) inBlock = false;
        continue;
      }
      out.push(line);
      continue;
    }
    if (/^\s*(`{3,}|~{3,})\s*$/.test(line)) inBlock = false;
  }
  return out.join("\n");
}
