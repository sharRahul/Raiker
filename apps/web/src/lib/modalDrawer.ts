export interface ModalDrawerOptions {
  /** Which drawer this is. One union rather than a free string so a second
   *  caller cannot register under a name the singleton below does not know. */
  id:
    | "navigation"
    | "build-background"
    | "build-files"
    | "all-pages"
    | "command-palette";
  container: HTMLElement;
  returnFocusTo: HTMLElement | null;
  backgroundElements: HTMLElement[];
  onDismiss: () => void;
}

export type DeactivateModalDrawer = (restoreFocus?: boolean) => void;

let active: { id: ModalDrawerOptions["id"]; dismiss: () => void; cleanup: DeactivateModalDrawer } | null = null;

const focusableSelector = [
  "a[href]", "button:not([disabled])", "input:not([disabled])",
  "select:not([disabled])", "textarea:not([disabled])", "[tabindex]:not([tabindex='-1'])",
].join(",");

export function activateModalDrawer(options: ModalDrawerOptions): DeactivateModalDrawer {
  if (active !== null) {
    const previous = active;
    previous.dismiss();
    previous.cleanup(false);
  }

  const priorOverflow = document.body.style.overflow;
  const backgroundState = options.backgroundElements.map((element) => ({
    element,
    inert: Boolean(element.inert),
    ariaHidden: element.getAttribute("aria-hidden"),
  }));
  document.body.style.overflow = "hidden";
  for (const { element } of backgroundState) {
    element.inert = true;
    element.setAttribute("aria-hidden", "true");
  }

  const focusables = () => Array.from(options.container.querySelectorAll<HTMLElement>(focusableSelector))
    .filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true");

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.preventDefault();
      options.onDismiss();
      return;
    }
    if (event.key !== "Tab") return;
    const items = focusables();
    if (items.length === 0) {
      event.preventDefault();
      options.container.focus();
      return;
    }
    const first = items[0];
    const last = items.at(-1)!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  document.addEventListener("keydown", onKeyDown);

  let cleaned = false;
  const record = { id: options.id, dismiss: options.onDismiss, cleanup: (() => {}) as DeactivateModalDrawer };
  const cleanup: DeactivateModalDrawer = (restoreFocus = true) => {
    if (cleaned) return;
    cleaned = true;
    document.removeEventListener("keydown", onKeyDown);
    document.body.style.overflow = priorOverflow;
    for (const state of backgroundState) {
      state.element.inert = state.inert;
      if (state.ariaHidden === null) state.element.removeAttribute("aria-hidden");
      else state.element.setAttribute("aria-hidden", state.ariaHidden);
    }
    if (active === record) active = null;
    if (restoreFocus) options.returnFocusTo?.focus();
  };
  record.cleanup = cleanup;
  active = record;
  queueMicrotask(() => (focusables()[0] ?? options.container).focus());
  return cleanup;
}
