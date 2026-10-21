// QUI-L05 / QUI-L10 — the help panel replaces the Guide page: opened from ?,
// on the current page's article, with search over every article.
import { render, screen, waitFor, within } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import HelpPanel from "./HelpPanel.svelte";
import { closeHelp, help, helpSlugFromHash, isHelpAddress, openHelp } from "../help.svelte";
import { stubFetch } from "../test-helpers";

const INDEX = {
  available: true,
  reason_code: "",
  sections: [
    { slug: "connecting-a-model", title: "Connecting a model", summary: "Local or hosted" },
    { slug: "memory", title: "Memory", summary: "What Raiker remembers" },
  ],
};

afterEach(() => {
  closeHelp();
  vi.unstubAllGlobals();
});

describe("the help panel", () => {
  it("opens on the article for the page you are on", async () => {
    stubFetch({
      "GET /api/guide": INDEX,
      "GET /api/guide/connecting-a-model": {
        slug: "connecting-a-model",
        title: "Connecting a model",
        summary: "",
        markdown: "# Connecting a model\n\nPick where Raiker thinks.",
      },
    });
    render(HelpPanel, { props: { current: "models" } });
    openHelp();
    const panel = await screen.findByRole("complementary", { name: "Help" });
    expect(await within(panel).findByText("Pick where Raiker thinks.")).toBeInTheDocument();
    await fireEvent.click(within(panel).getByRole("button", { name: /All articles/ }));
    expect(within(panel).getByRole("list", { name: "Help articles" })).toBeInTheDocument();
  });

  it("searches every article", async () => {
    stubFetch({ "GET /api/guide": INDEX });
    render(HelpPanel, { props: { current: "home-without-article" } });
    openHelp();
    const panel = await screen.findByRole("complementary", { name: "Help" });
    await waitFor(() => expect(within(panel).getAllByRole("listitem")).toHaveLength(2));
    await fireEvent.input(within(panel).getByRole("searchbox", { name: "Search help" }), {
      target: { value: "remember" },
    });
    expect(within(panel).getAllByRole("listitem")).toHaveLength(1);
    expect(within(panel).getByRole("button", { name: /Memory/ })).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    stubFetch({ "GET /api/guide": INDEX });
    render(HelpPanel, { props: { current: "home" } });
    openHelp(null);
    await screen.findByRole("complementary", { name: "Help" });
    await fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("complementary", { name: "Help" })).toBeNull());
    expect(help.open).toBe(false);
  });

  it("reads an old guide address as an article", () => {
    expect(isHelpAddress("#/guide?section=memory")).toBe(true);
    expect(isHelpAddress("#/guide")).toBe(true);
    expect(isHelpAddress("#/guided")).toBe(false);
    expect(helpSlugFromHash("#/guide?section=memory")).toBe("memory");
    expect(helpSlugFromHash("#/guide")).toBeNull();
  });
});
