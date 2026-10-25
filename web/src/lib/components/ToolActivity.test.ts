import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import ToolActivity from "./ToolActivity.svelte";
import type { ToolCallRow } from "../chatPresentation";

const WAITING: ToolCallRow = {
  actionId: "act_1",
  toolName: "write_file",
  family: "file-write",
  label: "Write file",
  action: "notes.md",
  state: "waiting",
  reasons: [],
};

describe("ToolActivity — an approval that expired (RT-QUI-31)", () => {
  it("reads waiting while the approval can still be decided", () => {
    render(ToolActivity, { rows: [WAITING] });
    expect(screen.getByText("waiting for your decision")).toBeInTheDocument();
  });

  it("reads not done once the approval expired with no decision", () => {
    render(ToolActivity, { rows: [WAITING], expiredActions: new Set(["act_1"]) });
    expect(screen.queryByText("waiting for your decision")).toBeNull();
    expect(screen.getByText("not done — no decision")).toBeInTheDocument();
  });

  it("reads not done on a reopened conversation, where the sweep settled the row as failed", () => {
    render(ToolActivity, { rows: [{ ...WAITING, state: "failed" }], expiredActions: new Set(["act_1"]) });
    expect(screen.getByText("not done — no decision")).toBeInTheDocument();
  });
});
