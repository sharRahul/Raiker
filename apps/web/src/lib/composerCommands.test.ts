/**
 * Composer ergonomics (GAP-BUILD B19, GAP-CHAT C14).
 *
 * The parsing rules are the whole risk surface here: a mis-parsed `/` or `@`
 * either eats what the owner typed or sends something they did not. Every case
 * below is one of those.
 */
import { describe, expect, it } from "vitest";
import {
  applyMention,
  matchCommands,
  mentionAt,
  shortcuts,
  slashCommands,
  slashFragment,
  stripSlashToken,
} from "./composerCommands";

describe("slash commands", () => {
  it("offers only commands the surface really has", () => {
    const chat = slashCommands("chat").map((command) => command.name);
    const build = slashCommands("build").map((command) => command.name);

    // Export is a Chat control; the three modes and the terminal are Build's.
    expect(chat).toContain("export");
    expect(chat).not.toContain("terminal");
    expect(build).toContain("terminal");
    expect(build).toContain("plan-mode");
    expect(build).not.toContain("export");
    // Scheduling and the task list are Chat's: Chat is where work is handed off
    // to run without the owner watching, and Build is where code is written.
    expect(chat).toContain("schedule");
    expect(chat).toContain("tasks");
    expect(build).not.toContain("schedule");
    expect(build).not.toContain("tasks");
    // Both carry the shared set.
    for (const shared of ["new", "model", "attach", "approvals", "stop", "shortcuts"]) {
      expect(chat).toContain(shared);
      expect(build).toContain(shared);
    }
  });

  it("every command names an action the view can dispatch on", () => {
    for (const surface of ["chat", "build"] as const) {
      for (const command of slashCommands(surface)) {
        expect(command.action).not.toBe("");
        expect(command.summary.length).toBeGreaterThan(0);
      }
    }
  });

  it("opens only at the start of the prompt", () => {
    expect(slashFragment("/mo", 3)).toBe("mo");
    expect(slashFragment("/", 1)).toBe("");
    // Mid-sentence slashes are text, not commands: a URL or an "either/or" must
    // not pop a menu over what is being written.
    expect(slashFragment("see https://x/y", 15)).toBeNull();
    expect(slashFragment("either/or", 9)).toBeNull();
  });

  it("closes once the token ends", () => {
    // A space or newline ends the command; what follows is the prompt.
    expect(slashFragment("/new draft the notes", 20)).toBeNull();
    expect(slashFragment("/new\nmore", 9)).toBeNull();
  });

  it("filters by prefix, and offers everything for a bare slash", () => {
    expect(matchCommands("chat", "").length).toBe(slashCommands("chat").length);
    expect(matchCommands("chat", "mo").map((c) => c.name)).toEqual(["model"]);
    expect(matchCommands("chat", "zzz")).toEqual([]);
  });

  it("removes the command token and keeps what was typed after it", () => {
    expect(stripSlashToken("/new")).toBe("");
    expect(stripSlashToken("/new draft the release notes")).toBe("draft the release notes");
  });
});

describe("@ mentions", () => {
  it("reads the token under the caret", () => {
    expect(mentionAt("@src/app", 8)).toEqual({ start: 0, end: 8, fragment: "src/app" });
    expect(mentionAt("look at @lib", 12)).toEqual({ start: 8, end: 12, fragment: "lib" });
  });

  it("needs the @ to open a word, so an email address is left alone", () => {
    expect(mentionAt("mail me@example.com", 19)).toBeNull();
  });

  it("closes at a space, because a completion cannot span one", () => {
    expect(mentionAt("@src and then", 13)).toBeNull();
  });

  it("is null when there is no @ before the caret", () => {
    expect(mentionAt("plain text", 10)).toBeNull();
  });

  it("replaces exactly the token, leaving the rest of the line intact", () => {
    const token = mentionAt("check @app then run", 10);
    expect(token).not.toBeNull();
    const applied = applyMention("check @app then run", token!, "apps/web/src/main.ts");
    // One space, not two: the token's own trailing space is consumed.
    expect(applied.text).toBe("check @apps/web/src/main.ts then run");
    // The caret lands after the inserted path, ready for the next word.
    expect(applied.text.slice(0, applied.caret)).toBe("check @apps/web/src/main.ts ");
  });

  it("leaves a trailing space when the mention ends the line", () => {
    const token = mentionAt("look at @main", 13);
    const applied = applyMention("look at @main", token!, "src/main.ts");
    expect(applied.text).toBe("look at @src/main.ts ");
    expect(applied.caret).toBe(applied.text.length);
  });
});

describe("the keyboard map", () => {
  it("documents Build's extra binding and not Chat's", () => {
    const chat = shortcuts("chat").map((row) => row.keys);
    const build = shortcuts("build").map((row) => row.keys);

    expect(build).toContain("Shift + Tab");
    expect(chat).not.toContain("Shift + Tab");
    for (const shared of ["Enter", "Shift + Enter", "/", "@", "Esc"]) {
      expect(chat).toContain(shared);
      expect(build).toContain(shared);
    }
  });
});
