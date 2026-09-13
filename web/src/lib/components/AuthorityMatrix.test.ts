// Delegated authority: what the owner turned on, and the strictly smaller thing
// the agent inherits from it.
//
// BUG-246 — the same list is offered twice, as a table and as stacked cards,
// because a three-column table at 390px scrolled its *verdict* column off
// screen and every row read "Unavail" under Raiker agent. CSS decides which one
// a width gets, and `display: none` takes the other out of the accessibility
// tree with it — so a reader meets each capability once. jsdom applies no media
// query, so both are in this DOM: the assertions count *per presentation*
// rather than pretending only one is mounted, and the last one asserts the
// property that makes the pair safe.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen, within } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import { makeGate } from "../test-helpers";
import AuthorityMatrix from "./AuthorityMatrix.svelte";

const GATES = [
  makeGate({ capability: "shell_execution", state: "enabled_runtime", decision_mode: "ask" }),
  makeGate({ capability: "process_execution", state: "disabled", decision_mode: "allow" }),
  makeGate({
    capability: "web_fetch",
    state: "enabled_runtime",
    decision_mode: "allow",
    readiness: { provider_ready: false },
  }),
];

describe("AuthorityMatrix", () => {
  it("separates owner control from the agent's derived authority", () => {
    const { container } = render(AuthorityMatrix, { gates: GATES });
    const table = container.querySelector<HTMLElement>(".matrix-scroll")!;

    expect(screen.getByRole("columnheader", { name: "Owner control" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Raiker agent" })).toBeInTheDocument();
    // The agent column, one verdict per gate: asked for, switched off, and on
    // but with a readiness requirement the backend reports as unmet.
    expect(within(table).getByText("Ask")).toBeInTheDocument();
    expect(within(table).getByText("Unavailable")).toBeInTheDocument();
    expect(within(table).getByText("Not ready")).toBeInTheDocument();
    // NEW-PERM-03 — the owner column now answers in the same two words the row
    // below it uses, rather than in a third vocabulary of its own.
    expect(within(table).getByText("On · Ask me")).toBeInTheDocument();
    expect(within(table).getByText("Off · Allow")).toBeInTheDocument();
  });

  it("tells Allow and Automatic apart instead of calling both Direct", () => {
    // NEW-PERM-03 — `Direct` was one word for two different grants, and the
    // page names them separately everywhere else.
    const { container } = render(AuthorityMatrix, {
      gates: [
        makeGate({ capability: "web_fetch", state: "enabled_runtime", decision_mode: "allow" }),
        makeGate({
          capability: "shell_execution",
          state: "enabled_runtime",
          decision_mode: "auto",
        }),
      ],
    });
    const table = container.querySelector<HTMLElement>(".matrix-scroll")!;
    expect(within(table).getByText("Allow")).toBeInTheDocument();
    expect(within(table).getByText("Automatic")).toBeInTheDocument();
    expect(within(table).queryByText("Direct")).toBeNull();
  });

  it("does not read an unrecognised mode as permission", () => {
    // The defect this closes: anything that was not `deny` or `ask` fell through
    // to `Direct`, so a missing, misspelt or newer-than-this-build value
    // rendered as the most permissive verdict the table can print.
    const { container } = render(AuthorityMatrix, {
      gates: [
        makeGate({ capability: "web_fetch", state: "enabled_runtime", decision_mode: "" }),
        makeGate({
          capability: "shell_execution",
          state: "enabled_runtime",
          decision_mode: "supervise",
        }),
      ],
    });
    const table = container.querySelector<HTMLElement>(".matrix-scroll")!;
    expect(within(table).getAllByText("Unknown")).toHaveLength(2);
    expect(within(table).queryByText("Direct")).toBeNull();
    expect(within(table).queryByText("Allow")).toBeNull();
    // And the verdict is styled as blocked rather than as a live authority.
    expect(container.querySelectorAll(".matrix-scroll .authority-state.blocked")).toHaveLength(2);
  });

  it("says the table summarises configuration, not what a turn may do", () => {
    // NEW-PERM-03 — the heading claimed *carried* authority for a table that
    // reads account configuration; a task's scope and the runtime's own checks
    // narrow it again at the moment of use.
    const { container } = render(AuthorityMatrix, { gates: GATES, total: 60 });
    const note = container.querySelector(".matrix-note")!;
    expect(note.textContent).toMatch(/this account configures/i);
    expect(note.textContent).toMatch(/can narrow it further/i);
    expect(container.querySelector(".eyebrow")!.textContent).toMatch(/read-only/i);
  });

  it("gives a narrow window the same verdicts without a sideways scroll", () => {
    const { container } = render(AuthorityMatrix, { gates: GATES });
    const cards = container.querySelector<HTMLElement>(".matrix-cards")!;

    // Every capability, and the verdict that was the part being scrolled away.
    expect(within(cards).getAllByRole("listitem")).toHaveLength(GATES.length);
    expect(within(cards).getByText("Ask")).toBeInTheDocument();
    expect(within(cards).getByText("Unavailable")).toBeInTheDocument();
    expect(within(cards).getByText("Not ready")).toBeInTheDocument();
    // Each verdict is labelled, so it reads as an answer rather than a word.
    expect(within(cards).getAllByText("Raiker agent")).toHaveLength(GATES.length);
  });

  it("hides one presentation rather than styling it away", () => {
    // The property that makes two renderings safe: `display: none` removes a
    // subtree from the accessibility tree, so nothing ever announces the same
    // capability twice. Only `display` has that effect — `opacity`, `clip` or a
    // zero height would leave both readings audible — so the declaration itself
    // is what is asserted.
    const source = readFileSync(
      resolve(process.cwd(), "src", "lib", "components", "AuthorityMatrix.svelte"),
      "utf8",
    );
    expect(source).toMatch(/\.matrix-cards \{ display:none; \}/);
    const narrow = source.slice(source.indexOf("@media (max-width:640px)"));
    expect(narrow).toContain(".matrix-scroll { display:none; }");
    expect(narrow).toContain(".matrix-cards { display:grid;");
  });
});
