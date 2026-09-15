/**
 * Coming back from a vendor page should not require pressing anything.
 *
 * Some setup genuinely happens outside Raiker: a local runtime is somebody
 * else's installer, and Raiker will not download and execute it. What must not
 * happen is for that one unavoidable trip to become the product's normal
 * lifecycle — *open this website, come back, press Look again, press Test, read
 * a stale status, press Refresh*. Each of those presses is Raiker asking the
 * owner to do a job Raiker can do itself.
 *
 * So this arms a one-shot listener: the moment the browser tab is looked at
 * again after the vendor page was opened, detection re-runs and the result is
 * reported. The owner's part ends at installing the thing.
 *
 * Three properties are deliberate.
 *
 * * **One shot.** It fires once and unsubscribes. A listener that ran on every
 *   tab switch would re-detect all day, which is a background poll wearing a
 *   different name.
 * * **It reports, it does not conclude.** Raiker opened a download; whether the
 *   owner ran it is theirs to say. The callback receives what detection *found*,
 *   and the caller writes an honest sentence from that — never "installed"
 *   because a tab regained focus.
 * * **Cancellable.** The returned function detaches the listener, so a view that
 *   unmounts before the owner returns leaves nothing behind to fire against a
 *   destroyed component.
 */

/** Detach an armed return listener. Safe to call more than once. */
export type CancelReturnDetect = () => void;

/**
 * Run `onReturn` the first time this tab is looked at again.
 *
 * `visibilitychange` is the primary signal and `focus` is the fallback: a
 * vendor page opened in a new tab makes this one hidden, but an owner on a
 * window manager that never hides it would only ever produce a focus event.
 * Both are attached; whichever arrives first wins and both are removed.
 */
export function onReturnToApp(onReturn: () => void): CancelReturnDetect {
  let done = false;

  const fire = () => {
    if (done) return;
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    done = true;
    detach();
    onReturn();
  };

  const detach = () => {
    document.removeEventListener("visibilitychange", fire);
    window.removeEventListener("focus", fire);
  };

  document.addEventListener("visibilitychange", fire);
  window.addEventListener("focus", fire);
  return () => {
    done = true;
    detach();
  };
}

/**
 * What a return-and-detect round found, in the words the owner reads.
 *
 * A shared writer rather than a string built at each call site, because the one
 * thing these sentences must never do is claim an install Raiker did not
 * observe — and that is exactly the kind of copy that drifts when it is written
 * twice.
 */
export function detectionNotice(options: {
  vendor: string;
  detected: boolean;
}): string {
  return options.detected
    ? `${options.vendor} is now installed on this machine.`
    : `${options.vendor} still isn't detected on this machine. If you've just installed it, it may need to be started once.`;
}
