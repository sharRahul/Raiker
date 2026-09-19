import { describe, expect, it } from "vitest";
import { guideSectionHref, resolveGuideLinks } from "./guideLinks";
import { renderMarkdown } from "./markdown";

const CHAPTERS = new Set([
  "getting-started",
  "connecting-a-model",
  "working-in-build",
  "troubleshooting",
]);

describe("resolveGuideLinks", () => {
  it("rewrites a sibling chapter into the address the Guide page uses", () => {
    expect(
      resolveGuideLinks("See [Connecting a model](connecting-a-model.md).", CHAPTERS),
    ).toBe("See [Connecting a model](#/guide?section=connecting-a-model).");
  });

  it("drops a heading fragment, because the Guide addresses a chapter", () => {
    expect(resolveGuideLinks("[Repairs](troubleshooting.md#repairs)", CHAPTERS)).toBe(
      "[Repairs](#/guide?section=troubleshooting)",
    );
  });

  // The point of reading the chapter list rather than guessing: a build that
  // shipped fewer chapters must not offer an address for one that is missing.
  it("leaves a chapter this build did not ship as prose naming its path", () => {
    expect(resolveGuideLinks("[Design](design.md)", CHAPTERS)).toBe("Design (docs/design.md)");
  });

  it("turns a repository document into a sentence that names it once", () => {
    expect(
      resolveGuideLinks("Full contract: [Known limits](../architecture/KNOWN_LIMITS.md).", CHAPTERS),
    ).toBe("Full contract: Known limits (docs/architecture/KNOWN_LIMITS.md).");
  });

  it("leaves an external link alone for the renderer to handle", () => {
    const source = "[the spec](https://example.com/a.md)";
    expect(resolveGuideLinks(source, CHAPTERS)).toBe(source);
  });

  it("leaves a link to something that is not Markdown alone", () => {
    const source = "[a picture](../screenshots/chat.png)";
    expect(resolveGuideLinks(source, CHAPTERS)).toBe(source);
  });

  it("addresses a chapter the way the route does", () => {
    expect(guideSectionHref("memory")).toBe("#/guide?section=memory");
  });
});

describe("renderMarkdown in-app links", () => {
  it("renders a resolved chapter reference as a link that opens in place", () => {
    const html = renderMarkdown(
      resolveGuideLinks("See [Troubleshooting](troubleshooting.md).", CHAPTERS),
      { inAppLinks: true },
    );
    expect(html).toContain('<a href="#/guide?section=troubleshooting" class="md-inapp-link">');
    expect(html).not.toContain("target=");
  });

  // The whole reason the opt-in exists. A model can write the same characters;
  // without the flag they stay characters.
  it("leaves the same address as plain text for a model-authored answer", () => {
    const html = renderMarkdown("Go to [Permissions](#/capabilities) now.");
    expect(html).not.toContain("<a ");
    expect(html).toContain("[Permissions](#/capabilities)");
  });

  it("refuses a scheme even when in-app links are allowed", () => {
    const html = renderMarkdown("[x](javascript:alert(1))", { inAppLinks: true });
    expect(html).not.toContain("<a ");
  });

  it("refuses a protocol-relative address even when in-app links are allowed", () => {
    const html = renderMarkdown("[x](#//evil.example.com)", { inAppLinks: true });
    expect(html).not.toContain("<a ");
  });

  it("does not leave the flag set for the next render", () => {
    renderMarkdown("[x](#/guide?section=memory)", { inAppLinks: true });
    expect(renderMarkdown("[x](#/guide?section=memory)")).not.toContain("<a ");
  });
});
