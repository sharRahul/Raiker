/**
 * Re-run `measure` whenever the layout under a docked surface may have moved.
 *
 * Invariant: a docked card or tray is measured against what is on the page now,
 * not as of its last tick. A surface that appears after the card does — a
 * composer mounting behind an approval card — is measured in the next frame,
 * not up to a second later with its **Send** covered in between (FIXED-661).
 *
 * Three triggers: any element added or removed (coalesced to one call per
 * frame), a resize, and a slow backstop tick for what no observer reports — a
 * font arriving, a transition settling. Returns the cleanup.
 */
export function watchLayout(measure: () => void, backstopMs = 1000): () => void {
  if (typeof window === "undefined") return () => {};
  const nextFrame =
    typeof window.requestAnimationFrame === "function"
      ? (callback: () => void) => window.requestAnimationFrame(callback)
      : (callback: () => void) => window.setTimeout(callback, 16);
  let queued = false;
  const schedule = () => {
    if (queued) return;
    queued = true;
    nextFrame(() => {
      queued = false;
      measure();
    });
  };
  measure();
  // Element arrivals and departures only: a docked surface restyling itself
  // (its own offset) must not be what wakes it again.
  const observer =
    typeof MutationObserver === "function" ? new MutationObserver(schedule) : null;
  observer?.observe(document.body, { childList: true, subtree: true });
  const tick = window.setInterval(measure, backstopMs);
  window.addEventListener("resize", measure);
  return () => {
    observer?.disconnect();
    window.clearInterval(tick);
    window.removeEventListener("resize", measure);
  };
}
