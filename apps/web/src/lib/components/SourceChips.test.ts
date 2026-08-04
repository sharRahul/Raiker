// C6 — the strip has to keep two claims apart. A source in the ledger is a fact
// the runtime recorded; a source the model *cited* is the model's claim about
// which sentence rests on it. Collapsing them would be the dishonest version of
// provenance, so the tests hold the strip to showing both and marking only one.
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import SourceChips from "./SourceChips.svelte";
import type { TurnSourceView } from "../apiTypes";

function source(over: Partial<TurnSourceView> = {}): TurnSourceView {
  return {
    source_id: "s1",
    ordinal: 1,
    kind: "file",
    title: "contracts/meridian.md",
    locator: "contracts/meridian.md",
    tool_name: "read_file",
    detail: "read in full",
    attachment_id: "",
    turn_id: "turn_1",
    openable: true,
    ...over,
  };
}

describe("SourceChips", () => {
  it("shows every recorded source, cited or not", () => {
    render(SourceChips, {
      sources: [source(), source({ source_id: "s2", ordinal: 2, title: "Renewal thread", kind: "email" })],
      citedIds: new Set(["s1"]),
      onopen: () => {},
    });
    expect(screen.getByRole("button", { name: /contracts\/meridian\.md/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Renewal thread/ })).toBeInTheDocument();
  });

  it("says in words which one the answer cited, not only in colour", () => {
    render(SourceChips, {
      sources: [source(), source({ source_id: "s2", ordinal: 2, title: "Renewal thread" })],
      citedIds: new Set(["s1"]),
      onopen: () => {},
    });
    expect(
      screen.getByRole("button", { name: /contracts\/meridian\.md — cited in this answer/ }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Renewal thread — cited in this answer/ }),
    ).not.toBeInTheDocument();
  });

  it("renders nothing at all when the turn read nothing", () => {
    const { container } = render(SourceChips, { sources: [], onopen: () => {} });
    expect(container.querySelector("section")).toBeNull();
  });

  it("opens the source it names", async () => {
    const onopen = vi.fn();
    render(SourceChips, { sources: [source()], onopen });
    screen.getByRole("button", { name: /contracts\/meridian\.md/ }).click();
    expect(onopen).toHaveBeenCalledWith(expect.objectContaining({ source_id: "s1" }));
  });

  it("does not offer to open a source that kept nothing to open", () => {
    // A dead control is worse than a stated one: a source with no passage and no
    // attachment is still listed, because the turn really read it, but it is
    // disabled rather than pretending it will show something.
    render(SourceChips, { sources: [source({ openable: false })], onopen: () => {} });
    expect(screen.getByRole("button", { name: /contracts\/meridian\.md/ })).toBeDisabled();
  });
});
