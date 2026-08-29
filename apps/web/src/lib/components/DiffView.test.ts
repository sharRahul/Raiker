// B14 — what the reader must put on screen: the file it changes, how much it
// changes, and both sides of the change told apart by something other than
// colour alone.
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import DiffView from "./DiffView.svelte";

const DIFF = [
  "diff --git a/src/app.py b/src/app.py",
  "--- a/src/app.py",
  "+++ b/src/app.py",
  "@@ -10,2 +10,2 @@",
  "     setup()",
  "-    run()",
  "+    run(timeout=30)",
  "",
].join("\n");

describe("DiffView", () => {
  it("names the file and states the size of the change", () => {
    render(DiffView, { props: { diff: DIFF } });
    expect(screen.getByText("src/app.py")).toBeInTheDocument();
    expect(screen.getByText("+1")).toBeInTheDocument();
    expect(screen.getByText("−1")).toBeInTheDocument();
  });

  it("labels added and removed lines for a screen reader", () => {
    render(DiffView, { props: { diff: DIFF } });
    expect(screen.getByText("Added:")).toBeInTheDocument();
    expect(screen.getByText("Removed:")).toBeInTheDocument();
  });

  it("says so rather than rendering an empty frame when there is no diff", () => {
    render(DiffView, { props: { diff: null, emptyLabel: "(nothing to record)" } });
    expect(screen.getByText("(nothing to record)")).toBeInTheDocument();
  });

  it("can be collapsed so a long change does not own the transcript", () => {
    render(DiffView, { props: { diff: DIFF, open: false } });
    expect(screen.getByRole("button", { expanded: false })).toBeInTheDocument();
    expect(screen.queryByText("Added:")).toBeNull();
  });
});
