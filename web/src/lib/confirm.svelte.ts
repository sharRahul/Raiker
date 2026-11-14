/**
 * QUI-F10 — one "Are you sure" for the whole app.
 *
 * Every confirmation used to be the browser's own `window.confirm`: a grey
 * system box that names the site instead of the action, can't say which
 * button is the dangerous one, and looks different in every browser. Every
 * question now goes through `askConfirm`, which the shell answers with one
 * dialog (`ConfirmDialog.svelte`): the question, what it affects, **Cancel**
 * and the action named on its own button. Enter confirms, Esc cancels.
 */
export interface ConfirmRequest {
  /** The question, as a sentence: "Delete “Weekly review”?" */
  title: string;
  /** What it affects or why it matters, when that is worth saying. */
  body?: string;
  /** The action's own name: "Delete", "Discard changes". Never "OK". */
  confirmLabel: string;
  /** True when the action destroys something; its button says so in colour and words. */
  danger?: boolean;
  /**
   * 2026-11-15 — a question that needs a few words back ("Why is this
   * incorrect?"). The dialog shows a labelled field; `askText` reads it.
   * Replaces the browser's `window.prompt`, the last native box in the app.
   */
  input?: { label: string; value?: string; placeholder?: string; required?: boolean };
}

interface Pending extends ConfirmRequest {
  resolve: (answer: boolean, text?: string) => void;
  /** What the owner typed, when the request asked for text. */
  text?: string;
}

export const confirmState = $state<{ current: Pending | null; hosts: number }>({ current: null, hosts: 0 });

/** The shell's dialog registers itself; returns the unregister. */
export function hostConfirm(): () => void {
  confirmState.hosts += 1;
  return () => {
    confirmState.hosts -= 1;
  };
}

/** The question in one string: the title, then what it affects. */
export function confirmText(request: ConfirmRequest): string {
  return request.body ? `${request.title} ${request.body}` : request.title;
}

/**
 * Ask, and resolve `true` only on an explicit confirm. A second ask cancels the
 * first. A component rendered without the shell (a test, an embedded page) has
 * no dialog to answer it, so it asks the browser in the same words instead of
 * hanging.
 */
export function askConfirm(request: ConfirmRequest): Promise<boolean> {
  if (confirmState.hosts === 0) {
    return Promise.resolve(typeof window !== "undefined" && typeof window.confirm === "function" && window.confirm(confirmText(request)));
  }
  confirmState.current?.resolve(false);
  return new Promise((resolve) => {
    confirmState.current = { ...request, resolve };
  });
}

/** The dialog's answer. */
export function answerConfirm(answer: boolean): void {
  const pending = confirmState.current;
  confirmState.current = null;
  pending?.resolve(answer, pending.text);
}

/**
 * Ask for a few words; resolve the trimmed text, or `null` on Cancel (or an
 * empty answer to a required field). Without the shell's dialog it falls back
 * to the browser's prompt in the same words, as `askConfirm` does.
 */
export async function askText(request: ConfirmRequest & { input: NonNullable<ConfirmRequest["input"]> }): Promise<string | null> {
  if (confirmState.hosts === 0) {
    if (typeof window === "undefined" || typeof window.prompt !== "function") return null;
    const typed = window.prompt(confirmText(request), request.input.value ?? "");
    return typed === null ? null : typed.trim();
  }
  confirmState.current?.resolve(false);
  const [confirmed, text] = await new Promise<[boolean, string]>((resolve) => {
    confirmState.current = {
      ...request,
      text: request.input.value ?? "",
      resolve: (answer: boolean, typed?: string) => resolve([answer, typed ?? ""]),
    };
  });
  const typed = text.trim();
  if (!confirmed) return null;
  if (request.input.required && typed === "") return null;
  return typed;
}
