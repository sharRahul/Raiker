// BUG-245 — a cited past conversation names its exchanges and can now open one.
//
// The two halves that did not meet: `conversation_search` became a citable
// source (FIXED-317), and a turn coordinate became openable (FIXED-316). The
// panel showed each exchange's title and date as text, so verifying one meant
// retyping the title into chat search.
import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import type { SourceAnchorView } from "../apiTypes";
import SourceAnchorLinks from "./SourceAnchorLinks.svelte";

function anchor(partial: Partial<SourceAnchorView> = {}): SourceAnchorView {
  return {
    session_id: "sess_1",
    turn_id: "turn_1",
    title: "Renewal terms",
    created_at: "2026-03-14T09:12:00Z",
    origin: "chat",
    ...partial,
  };
}

describe("SourceAnchorLinks", () => {
  it("opens each exchange at its own turn, not at the top of the conversation", () => {
    render(SourceAnchorLinks, { props: { anchors: [anchor()] } });
    const link = screen.getByRole("link", { name: /Renewal terms/ });
    expect(link).toHaveAttribute("href", "#/new-chat?session=sess_1&turn=turn_1");
  });

  it("names the conversation and the day, which is what identifies it", () => {
    render(SourceAnchorLinks, { props: { anchors: [anchor()] } });
    expect(screen.getByRole("link", { name: /Renewal terms · 2026-03-14/ })).toBeVisible();
  });

  it("opens a Build conversation in Build", () => {
    render(SourceAnchorLinks, {
      props: { anchors: [anchor({ origin: "build", session_id: "sess_b" })] },
    });
    expect(screen.getByRole("link", { name: /Renewal terms/ })).toHaveAttribute(
      "href",
      "#/build?session=sess_b&turn=turn_1",
    );
  });

  it("still names an untitled conversation rather than rendering a bare date", () => {
    render(SourceAnchorLinks, { props: { anchors: [anchor({ title: "  " })] } });
    expect(screen.getByRole("link", { name: /Untitled conversation/ })).toBeVisible();
  });

  it("renders nothing at all when a source has no exchanges to offer", () => {
    render(SourceAnchorLinks, { props: { anchors: [] } });
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });
});
