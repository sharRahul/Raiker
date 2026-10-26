/**
 * QUI-F19 — undo windows.
 *
 * An approved connector write is held on the server for this long before it is
 * sent (`raiker/runtime/held_sends.py`, `HOLD_SECONDS`), and Undo or Stop inside
 * it takes it back. The number here only drives the countdown the owner sees;
 * the server decides when the window closes.
 */
export const HELD_SEND_SECONDS = 10;

/** Writes the server holds before sending: anything sent through a connection. */
export function holdsBeforeSending(toolName: string): boolean {
  return toolName === "connector_write";
}
