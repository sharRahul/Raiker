/**
 * Names for the records a live round creates, so a round cannot find its own
 * leftovers and mistake them for the thing under test.
 *
 * BUG-250. The live suite shares one workspace now — that was the point of
 * FIXED-327, FIXED-328 and the conversions after them — and the layer under
 * those was this: a spec that creates **Overnight research** and then asserts on
 * **Overnight research** is asserting on whatever the last three runs left
 * behind as well. On 2026-09-15 that resolved to three threads and Playwright's
 * strict mode refused to choose, which is the good failure. The bad one is the
 * same spec passing on somebody else's evidence.
 *
 * The answer is cheap, general and needs no workspace reset: give the record a
 * per-run suffix. A spec can then be re-run against a workspace with a year of
 * history in it and still be about the row it just made.
 *
 * Use it for anything the product will **store under a name** — a task title, a
 * project display name, a checkpoint label, a channel or collector name. Do not
 * use it for prompts, passwords, paths or provider keys: those are inputs, not
 * records, and a suffix in them would only make the assertion harder to read.
 */

/**
 * `base` with a short per-run suffix — `"Repo work"` → `"Repo work k2f9h1"`.
 *
 * Base-36 of the clock: short enough to read in a screenshot, and different on
 * every run of every spec in the round. Call it once at module scope and reuse
 * the constant, so every step of a spec names the same record.
 */
export function roundName(base: string): string {
  return `${base} ${Date.now().toString(36)}`;
}
