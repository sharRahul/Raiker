import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import Badge from "./Badge.svelte";
import { BADGES } from "../badges";

describe("Badge", () => {
  it("renders the variant's default label and a non-colour symbol cue", () => {
    render(Badge, { variant: "needs-approval" });
    expect(screen.getByText(BADGES["needs-approval"].label)).toBeInTheDocument();
    expect(screen.getByText(BADGES["needs-approval"].symbol)).toBeInTheDocument();
  });

  it("supports a raw-status label override while keeping the shape cue", () => {
    render(Badge, { variant: "active", label: "running" });
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.queryByText(BADGES.active.label)).not.toBeInTheDocument();
    expect(screen.getByText(BADGES.active.symbol)).toBeInTheDocument();
  });
});
