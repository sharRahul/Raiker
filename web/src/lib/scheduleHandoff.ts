/**
 * Chat's `/schedule` → the Tasks surface, opened on **Schedule once**.
 *
 * The composers hand a draft to each other with a window event, because both are
 * already mounted and can hear it. Tasks is code-split and mounts only when its
 * route is entered, so an event dispatched at navigation time would fire into an
 * empty room — the command would look like it worked and quietly do nothing.
 *
 * So the request is a one-shot flag the destination consumes when it mounts.
 * It carries no data and no authority: it selects a cadence chip. Nothing is
 * created, nothing is scheduled, and the owner still fills the form in and
 * presses the button themselves.
 */
let pending = false;

/** Ask the next Tasks mount to open on **Schedule once**. */
export function requestSchedule(): void {
  pending = true;
}

/** Consume the request, if there is one. Reading it clears it. */
export function takeScheduleRequest(): boolean {
  const requested = pending;
  pending = false;
  return requested;
}
