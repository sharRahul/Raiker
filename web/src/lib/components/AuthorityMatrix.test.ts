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
    expect(within(table).getByText("Ask")).toBeInTheDocument();
    expect(within(table).getAllByText("Unavailable")).toHaveLength(2);
    expect(within(table).getByText("Not ready")).toBeInTheDocument();
  });

  it("gives a narrow window the same verdicts without a sideways scroll", () => {
    const { container } = render(AuthorityMatrix, { gates: GATES });
    const cards = container.querySelector<HTMLElement>(".matrix-cards")!;

    // Every capability, and the verdict that was the part being scrolled away.
    expect(within(cards).getAllByRole("listitem")).toHaveLength(GATES.length);
    expect(within(cards).getByText("Ask")).toBeInTheDocument();
    expect(within(cards).getAllByText("Unavailable")).toHaveLength(2);
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
