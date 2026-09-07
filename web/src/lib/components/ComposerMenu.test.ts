/**
 * The composer's completion menu (B19).
 *
 * Two behaviours carry the weight: a refusal is shown *instead of* rows, and it
 * is shown in the plain language the surface renders — the governed message is
 * written with Markdown emphasis, and this row is not a Markdown surface.
 */
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import ComposerMenu from "./ComposerMenu.svelte";

describe("ComposerMenu", () => {
  it("renders nothing when there is nothing to offer", () => {
    const { container } = render(ComposerMenu, { items: [], onchoose: vi.fn() });
    expect(container.querySelector(".composer-menu")).toBeNull();
  });

  it("lists items with their detail and marks the active row", () => {
    render(ComposerMenu, {
      items: [
        { id: "new", label: "/new", detail: "Start a new conversation" },
        { id: "model", label: "/model", detail: "Choose the model" },
      ],
      active: 1,
      heading: "Commands",
      onchoose: vi.fn(),
    });

    expect(screen.getByRole("listbox", { name: "Commands" })).toBeInTheDocument();
    expect(screen.getByText("Start a new conversation")).toBeInTheDocument();
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveAttribute("aria-selected", "false");
    expect(options[1]).toHaveAttribute("aria-selected", "true");
  });

  it("shows a refusal instead of rows, with the control that fixes it", () => {
    render(ComposerMenu, {
      items: [{ id: "x", label: "should not render" }],
      notice: { text: "The code map is off.", href: "#/capabilities", linkLabel: "Permissions" },
      onchoose: vi.fn(),
    });

    expect(screen.getByText(/The code map is off/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Permissions" })).toBeInTheDocument();
    // A menu that could not be filled must not also show rows.
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("strips the governed message's Markdown emphasis rather than showing it", () => {
    render(ComposerMenu, {
      items: [],
      notice: {
        text: "Turn on **Code map indexing** in Permissions → Workspace.",
      },
      onchoose: vi.fn(),
    });

    expect(screen.getByText(/Turn on Code map indexing in Permissions/)).toBeInTheDocument();
    expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
  });
});
