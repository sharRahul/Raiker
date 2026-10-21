/** QUI-L04 — one choice in the Add dialog's catalogue. */
export interface AddOption {
  id: string;
  name: string;
  description: string;
  category: string;
  /** A short status after the name, such as "Connected". */
  note?: string | null;
  /** True when the option cannot be chosen; `note` should say why. */
  disabled?: boolean;
}
