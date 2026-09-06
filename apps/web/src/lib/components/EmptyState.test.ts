/**
 * VIS-12 — an empty state that names what is missing and stops is a dead end.
 *
 * The component has carried an `action` slot for a while and, before this pass,
 * *not one* of the thirteen call sites used it. Every zero-data screen in a
 * product with this many of them — no projects, tasks, sessions, checkpoints,
 * threads — told the owner what was absent and left them to work out what to do
 * about it.
 *
 * These tests are about the component's contract. The call sites are covered by
 * their own view tests; what is asserted here is that the block renders one
 * sentence, one action, and no jargon of its own.
 */
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import EmptyState from "./EmptyState.svelte";
import EmptyStateHarness from "./EmptyStateHarness.test.svelte";

describe("empty state", () => {
  it("renders a title and a body without an action", () => {
    render(EmptyState, { title: "No projects yet", body: "Keep one goal together." });

    expect(screen.getByText("No projects yet")).toBeInTheDocument();
    expect(screen.getByText("Keep one goal together.")).toBeInTheDocument();
  });

  it("renders the primary action when one is given", () => {
    render(EmptyStateHarness, {
      title: "No projects yet",
      body: "Keep one goal together.",
      actionLabel: "Name your first project",
    });

    const action = screen.getByRole("button", { name: "Name your first project" });
    expect(action).toBeInTheDocument();
    // The action belongs inside the same block as the explanation, not adrift
    // somewhere else on the page.
    expect(screen.getByText("No projects yet").closest("div")).toContainElement(action);
  });

  it("omits the body entirely rather than rendering an empty paragraph", () => {
    const { container } = render(EmptyState, { title: "Nothing here" });
    expect(container.querySelectorAll("p")).toHaveLength(1);
  });
});
