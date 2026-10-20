/**
 * UX-CHAT-01 — C17's recall ledger, out of ChatView.
 *
 * What Raiker remembered for each turn of this conversation, and the two
 * corrections an owner can make from under an answer. Loaded with the
 * transcript and refreshed after a correction, so the strip says what Raiker
 * knows now rather than what it knew when the turn ran. A failed read leaves
 * the strip absent: recall that cannot be shown must never be implied.
 */
import { api } from "../../api";
import type { RecalledMemory, TurnMemoryDisclosure } from "../../apiTypes";

export class RecallLedger {
  memories = $state<RecalledMemory[]>([]);
  // MEM-MODE-02 — which recall mode and backend each turn ran under.
  disclosures = $state<TurnMemoryDisclosure[]>([]);
  notice = $state<string | null>(null);

  constructor(private readonly session: () => string | null) {}

  refresh = async (id: string) => {
    try {
      const recall = await api.sessionRecall(id);
      this.memories = recall.memories;
      this.disclosures = recall.disclosures ?? [];
    } catch {
      this.memories = [];
      this.disclosures = [];
    }
  };

  /** A new conversation starts with nothing recalled and nothing to report. */
  reset = () => {
    this.memories = [];
    this.disclosures = [];
    this.notice = null;
  };

  disclosureFor = (turnId: string | undefined): TurnMemoryDisclosure | null => {
    if (turnId === undefined || turnId === "") return null;
    return this.disclosures.find((disclosure) => disclosure.turn_id === turnId) ?? null;
  };

  forTurn = (turnId: string | undefined): RecalledMemory[] => {
    if (turnId === undefined || turnId === "") return [];
    return this.memories.filter((memory) => memory.turn_id === turnId);
  };

  forget = async (memory: RecalledMemory) => {
    this.notice = null;
    try {
      await api.forgetMemory(memory.memory_id);
      this.notice = "Forgotten.";
    } catch {
      this.notice = "Could not forget that memory.";
    }
    const session = this.session();
    if (session !== null) await this.refresh(session);
  };

  correct = async (memory: RecalledMemory, text: string) => {
    if (text === "" || text === memory.text) return;
    this.notice = null;
    try {
      await api.editMemory(memory.memory_id, text);
      this.notice = "Corrected.";
    } catch {
      this.notice = "Could not correct that memory.";
    }
    const session = this.session();
    if (session !== null) await this.refresh(session);
  };
}
