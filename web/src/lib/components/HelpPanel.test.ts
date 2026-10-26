// QUI-L05 / QUI-L10 — the help panel replaces the Guide page: opened from ?,
// on the current page's article, with search over every article.
import { render, screen, waitFor, within } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import HelpPanel from "./HelpPanel.svelte";
import {
  closeHelp,
  help,
  helpPartFromHash,
  helpSlugFromHash,
  isHelpAddress,
  openHelp,
} from "../help.svelte";
import { stubFetch } from "../test-helpers";

const INDEX = {
  available: true,
  reason_code: "",
  sections: [
    {
      slug: "connecting-a-model",
      title: "Connecting a model",
      summary: "Local or hosted",
      parts: [{ id: "fallback-sequence", title: "Fallback sequence", summary: "When a model fails" }],
    },
    { slug: "memory", title: "Memory", summary: "What Raiker remembers", parts: [] },
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
        parts: INDEX.sections[0].parts,
        part: "",
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

  // The owner's directive: the panel never hands over a whole chapter. An
  // article is its intro and a list of parts; a part opens on its own.
  it("opens an article as its intro and parts, and a part on its own", async () => {
    const fetch = stubFetch({
      "GET /api/guide": INDEX,
      "GET /api/guide/connecting-a-model": {
        slug: "connecting-a-model",
        title: "Connecting a model",
        summary: "",
        parts: INDEX.sections[0].parts,
        part: "",
        markdown: "# Connecting a model\n\nPick where Raiker thinks.",
      },
      "GET /api/guide/connecting-a-model?part=fallback-sequence": {
        slug: "connecting-a-model",
        title: "Connecting a model",
        summary: "",
        parts: INDEX.sections[0].parts,
        part: "fallback-sequence",
        markdown: "## Fallback sequence\n\nThe next model takes over.",
      },
    });
    render(HelpPanel, { props: { current: "models" } });
    openHelp();
    const panel = await screen.findByRole("complementary", { name: "Help" });
    const parts = await within(panel).findByRole("list", { name: "In this article" });
    await fireEvent.click(within(parts).getByRole("button", { name: /Fallback sequence/ }));
    expect(await within(panel).findByText("The next model takes over.")).toBeInTheDocument();
    expect(within(panel).queryByText("Pick where Raiker thinks.")).toBeNull();
    expect(fetch.mock.calls.some(([url]) => String(url).includes("part=fallback-sequence"))).toBe(true);
    // Back goes to the article, not the whole list.
    await fireEvent.click(within(panel).getByRole("button", { name: /Connecting a model/ }));
    expect(await within(panel).findByText("Pick where Raiker thinks.")).toBeInTheDocument();
  });

  it("finds a part by its heading and opens it from a chip's locator", async () => {
    stubFetch({ "GET /api/guide": INDEX });
    render(HelpPanel, { props: { current: "home-without-article" } });
    openHelp();
    const panel = await screen.findByRole("complementary", { name: "Help" });
    await waitFor(() => expect(within(panel).getAllByRole("listitem")).toHaveLength(2));
    await fireEvent.input(within(panel).getByRole("searchbox", { name: "Search help" }), {
      target: { value: "fallback" },
    });
    const results = within(panel).getByRole("list", { name: "Search results" });
    expect(within(results).getByRole("button", { name: /Connecting a model.*Fallback sequence/ })).toBeInTheDocument();
    openHelp("memory#scope");
    expect(help.slug).toBe("memory");
    expect(help.part).toBe("scope");
  });

  it("never lets a slow article land over a search already typed", async () => {
    let release: (value: unknown) => void = () => {};
    const slow = new Promise((resolve) => (release = resolve));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/guide/")) {
          await slow;
          return { ok: true, status: 200, json: async () => ({ ...INDEX.sections[0], part: "", markdown: "# Late" }) } as Response;
        }
        return { ok: true, status: 200, json: async () => INDEX } as Response;
      }),
    );
    render(HelpPanel, { props: { current: "models" } });
    openHelp();
    const panel = await screen.findByRole("complementary", { name: "Help" });
    await fireEvent.input(within(panel).getByRole("searchbox", { name: "Search help" }), {
      target: { value: "fallback" },
    });
    release(null);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(await within(panel).findByRole("list", { name: "Search results" })).toBeInTheDocument();
    expect(within(panel).queryByText("Late")).toBeNull();
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
    expect(helpPartFromHash("#/guide?section=memory&part=the-knowledge-map")).toBe("the-knowledge-map");
    expect(helpPartFromHash("#/guide?section=memory&part=../x")).toBeNull();
  });
});
