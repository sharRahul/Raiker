/**
 * UX-CHAT-01 / UX-BUILD-01 — the two server reads behind a composer's menus.
 *
 * Chat and Build each carried their own copy of the `@` mention lookup and the
 * owner's skill slash commands, line for line, differing only in where an
 * unbuilt code map sends the owner. One controller, so the two composers cannot
 * drift into two keyboards (the rule `composerCommands.ts` states) and a fix to
 * either read lands in both.
 *
 * Moved, not changed: a newer lookup still wins over a late answer, a refusal
 * is still said with the control that fixes it, and a failed skills read still
 * leaves only the built-in commands.
 */
import { api } from "./api";
import { NOT_ANSWERING } from "./errorCopy";
import type { MenuItem } from "./components/ComposerMenu.svelte";
import type { SlashCommand } from "./composerCommands";
import type { PersonaView } from "./generated/apiContract";

export interface MentionNotice {
  text: string;
  href?: string;
  linkLabel?: string;
}

export class ComposerLookups {
  mentionItems = $state<MenuItem[]>([]);
  mentionNotice = $state<MentionNotice | null>(null);
  /** The owner's active skills that declare a command trigger. */
  slashCommands = $state<SlashCommand[]>([]);
  /** ADR-0005 — the owner's personas, offered first under `@`. */
  personas = $state<PersonaView[]>([]);
  private mentionRequest = 0;

  constructor(
    /** Where an unbuilt code map is built from, on this surface. */
    private readonly codeMapHome: { href: string; label: string },
  ) {}

  loadSlashCommands = async () => {
    try {
      this.slashCommands = (await api.skills())
        .filter((skill) => skill.active && skill.command_trigger)
        .map((skill) => ({
          name: skill.command_trigger as string,
          summary: `Use ${skill.name} · permissions unchanged`,
          action: "skill" as const,
        }));
    } catch {
      this.slashCommands = [];
    }
  };

  loadPersonas = async () => {
    try {
      const view = await api.personas();
      this.personas = Array.isArray(view?.personas) ? view.personas : [];
    } catch {
      // A persona list that cannot be read leaves file mentions working.
      this.personas = [];
    }
  };

  /** Personas whose name starts with what was typed after `@`, as menu rows. */
  personaItems(fragment: string): MenuItem[] {
    const wanted = fragment.toLowerCase();
    return this.personas
      .filter((persona) => persona.name.toLowerCase().startsWith(wanted))
      .map((persona) => ({
        id: persona.persona_id,
        label: `@${persona.name}`,
        detail: persona.description || undefined,
        group: "Personas",
        kind: "persona" as const,
      }));
  }

  loadMentions = async (fragment: string) => {
    const request = ++this.mentionRequest;
    try {
      const view = await api.codeMapPaths(fragment);
      if (request !== this.mentionRequest) return;
      if (view.status !== "success") {
        // A refusal is not an empty menu. An owner who has never built the
        // index and an owner whose search matched nothing need different next
        // steps, so the reason is shown with the control that fixes it.
        this.mentionItems = [];
        const gated = view.error?.type === "code_map_gate_disabled";
        this.mentionNotice = {
          text: view.error?.message ?? "Workspace file mentions are unavailable.",
          href: gated ? "#/capabilities" : this.codeMapHome.href,
          linkLabel: gated ? "Permissions" : this.codeMapHome.label,
        };
        return;
      }
      this.mentionNotice = null;
      this.mentionItems = (view.paths ?? []).map((entry) => ({
        id: entry.path,
        label: entry.path,
        detail: entry.language,
        group: "Files",
      }));
    } catch {
      if (request !== this.mentionRequest) return;
      this.mentionItems = [];
      this.mentionNotice = { text: `Files could not be looked up. ${NOT_ANSWERING}` };
    }
  };
}
