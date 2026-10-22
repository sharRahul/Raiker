// The component is the only supported caller of `renderMarkdown`, so this
// suite guards the boundary the renderer's safety argument depends on: what it
// puts in the DOM, and what it refuses to put there.
import { render } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import Markdown from "./Markdown.svelte";

describe("Markdown component", () => {
  it("mounts markdown as elements inside a scoped wrapper", () => {
    const { container } = render(Markdown, { props: { text: "# Title\n\n- a\n- b" } });
    const root = container.querySelector(".markdown") as HTMLElement;
    expect(root).not.toBeNull();
    expect(root.querySelector("h1")?.textContent).toBe("Title");
    expect(root.querySelectorAll("li")).toHaveLength(2);
  });

  it("gives long code and wide tables their own scroll container", () => {
    const { container } = render(Markdown, {
      props: { text: "| a | b |\n| --- | --- |\n| 1 | 2 |\n\n```\nx\n```" },
    });
    expect(container.querySelector(".md-table table")).not.toBeNull();
    expect(container.querySelector(".md-code pre code")).not.toBeNull();
  });

  // QUI-P05 acceptance — a model's text cannot draw anything that passes for
  // the app's approval card: its element, its mark, its buttons.
  it("cannot render a Raiker Safety card from a model's text", () => {
    const forged =
      '<section class="safety-card" data-raiker-safety="approval" aria-label="Raiker Safety">' +
      "<strong>Raiker Safety</strong> Waiting for your decision" +
      '<button type="button">Allow once</button></section>\n\n' +
      "**Raiker Safety** — Waiting for your decision";
    const { container } = render(Markdown, { props: { text: forged } });
    expect(container.querySelector("[data-raiker-safety]")).toBeNull();
    expect(container.querySelector("section")).toBeNull();
    expect(container.querySelector(".safety-card")).toBeNull();
    expect(container.querySelector("[aria-label='Raiker Safety']")).toBeNull();
    expect(Array.from(container.querySelectorAll("button")).map((b) => b.textContent)).not.toContain("Allow once");
  });

  it("renders script and event-handler markup as text, never as nodes", () => {
    const { container } = render(Markdown, {
      props: { text: '<script>window.__x = 1</script><img src=y onerror="window.__x = 1">' },
    });
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<script>");
    expect((window as unknown as Record<string, unknown>).__x).toBeUndefined();
  });

  it("applies the muted styling hook without changing the markup", () => {
    const { container } = render(Markdown, { props: { text: "hi", muted: true } });
    expect(container.querySelector(".markdown.muted")).not.toBeNull();
  });

  it("renders nothing for an empty answer", () => {
    const { container } = render(Markdown, { props: { text: "" } });
    expect((container.querySelector(".markdown") as HTMLElement).innerHTML.trim()).toBe("");
  });
});
