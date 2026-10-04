/**
 * UX-BUILD-01 — Build's turn source ledger, out of BuildView.
 *
 * Build reads the same material Chat does and receives the same `cite_as`
 * markers, so it owes the same account of where an answer came from. Build has
 * no inspector pane, so a cited source opens inline, under the answer that
 * cited it — which is why this is its own small controller rather than Chat's
 * `SourceInspector`: there is no file pane to coordinate with.
 */
import { api } from "../../api";
import type { TurnSourceExcerptView, TurnSourceView } from "../../apiTypes";
import { sentenceAround } from "../../citations";

export class InlineSources {
  turnSources = $state<TurnSourceView[]>([]);
  /**
   * Which source is open, as (turn, id): ids restart at `s1` in every turn, so
   * the id alone would open the panel under every turn that has one.
   */
  openSourceId = $state<string | null>(null);
  openSourceTurnId = $state<string | null>(null);
  excerpt = $state<TurnSourceExcerptView | null>(null);
  loading = $state(false);

  constructor(private readonly session: () => string | null) {}

  refresh = async (id: string) => {
    try {
      this.turnSources = (await api.sessionSources(id)).sources;
    } catch {
      // Provenance for an answer that already arrived: losing it must not cost
      // the transcript, so the chips simply do not appear.
      this.turnSources = [];
    }
  };

  close = () => {
    this.openSourceId = null;
    this.openSourceTurnId = null;
    this.excerpt = null;
    this.loading = false;
  };

  isOpen = (source: TurnSourceView): boolean =>
    this.openSourceId === source.source_id && this.openSourceTurnId === source.turn_id;

  show = async (source: TurnSourceView, quote = "") => {
    const session = this.session();
    if (session === null || !source.openable) return;
    if (this.isOpen(source)) {
      this.close();
      return;
    }
    this.openSourceId = source.source_id;
    this.openSourceTurnId = source.turn_id;
    this.excerpt = null;
    this.loading = true;
    try {
      const resolved = await api.turnSourceExcerpt(session, source.turn_id, source.source_id, quote);
      if (this.isOpen(source)) this.excerpt = resolved;
    } catch {
      if (this.isOpen(source)) this.excerpt = null;
    } finally {
      if (this.isOpen(source)) this.loading = false;
    }
  };

  /**
   * A `[s1]` chip inside the answer opens the same source the strip does — and
   * knows which sentence rests on it, so the panel opens at that part.
   */
  showById = (turnId: string, sourceId: string, answer: string) => {
    const match = this.turnSources.find(
      (source) => source.turn_id === turnId && source.source_id === sourceId,
    );
    if (match !== undefined) void this.show(match, sentenceAround(answer, sourceId));
  };
}
