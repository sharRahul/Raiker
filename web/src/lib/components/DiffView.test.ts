// B14 — what the reader must put on screen: the file it changes, how much it
// changes, and both sides of the change told apart by something other than
// colour alone.
import { fireEvent, render, screen } from "@testing-library/svelte";
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

// B14 remainder — accepting part of a change.
//
// An approval governed the whole change set, so a reviewer who wanted two of
// five hunks had to reject everything and ask again. The checkbox is offered
// only where the server can honour it, which is the property worth defending:
// a control the server would refuse is worse than no control.
describe("DiffView per-hunk acceptance", () => {
  const TWO_HUNKS = [
    "--- a/src/app.py",
    "+++ b/src/app.py",
    "@@ -1,2 +1,2 @@",
    "-a",
    "+A",
    " keep",
    "@@ -9,2 +9,2 @@",
    "-b",
    "+B",
    " keep",
    "",
  ].join("\n");

  it("stays a reader unless per-hunk acceptance is asked for", () => {
    render(DiffView, { props: { diff: TWO_HUNKS } });
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("offers one checkbox per hunk, all accepted to begin with", () => {
    render(DiffView, { props: { diff: TWO_HUNKS, selectable: true } });
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes).toHaveLength(2);
    expect(boxes.every((box) => (box as HTMLInputElement).checked)).toBe(true);
    expect(screen.getByText(/All 2 hunks/)).toBeInTheDocument();
  });

  it("declining a hunk says so, and says how many are left", async () => {
    render(DiffView, { props: { diff: TWO_HUNKS, selectable: true } });
    await fireEvent.click(screen.getAllByRole("checkbox")[0]);
    expect(screen.getByText(/1 of 2 hunks/)).toBeInTheDocument();
    expect((screen.getAllByRole("checkbox")[0] as HTMLInputElement).checked).toBe(false);
    expect((screen.getAllByRole("checkbox")[1] as HTMLInputElement).checked).toBe(true);
  });

  it("names each hunk's checkbox for a screen reader", () => {
    render(DiffView, { props: { diff: TWO_HUNKS, selectable: true } });
    expect(screen.getByLabelText("Accept hunk 1 of src/app.py")).toBeInTheDocument();
    expect(screen.getByLabelText("Accept hunk 2 of src/app.py")).toBeInTheDocument();
  });

  it("offers nothing to choose between when there is only one hunk", () => {
    // Accepting the only hunk is what Accept already does.
    render(DiffView, { props: { diff: DIFF, selectable: true } });
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("offers nothing on a diff the server could not apply", () => {
    // No `---`/`+++` pair: the applier requires those headers, so a checkbox
    // here would produce a hunk id the server must refuse.
    const loose = [
      "diff --git a/one.txt b/one.txt",
      "@@ -1 +1 @@",
      "-a",
      "+b",
      "diff --git a/two.txt b/two.txt",
      "@@ -1 +1 @@",
      "-c",
      "+d",
      "",
    ].join("\n");
    render(DiffView, { props: { diff: loose, selectable: true } });
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});
