import { describe, expect, it } from "vitest";
import {
  highlight,
  isHighlightable,
  languageForFilename,
  languageLabel,
  TOKEN_KINDS,
} from "./highlight";

describe("highlight — BUG-23 local grammar path", () => {
  it("emits only span tags carrying an allowlisted token class", () => {
    const html = highlight("const x = 1; // note", "ts");
    const classes = [...html.matchAll(/class="([^"]+)"/g)].map((m) => m[1]);
    expect(classes.length).toBeGreaterThan(0);
    for (const value of classes) {
      expect(TOKEN_KINDS).toContain(value.replace("tok-", ""));
    }
    expect(html.replace(/<\/?span[^>]*>/g, "")).not.toContain("<");
  });

  it("escapes source before wrapping it, so markup in code stays data", () => {
    const html = highlight("const a = '<script>alert(1)</script>';", "ts");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  it("escapes source in the plain-text fallback too", () => {
    const html = highlight("<img onerror=x>", "brainfuck");
    expect(html).toBe("&lt;img onerror=x&gt;");
  });

  it("does not guess at a language it does not ship", () => {
    expect(isHighlightable("cobol")).toBe(false);
    expect(highlight("MOVE X TO Y.", "cobol")).toBe("MOVE X TO Y.");
  });

  it("still labels a language it cannot tokenise", () => {
    expect(languageLabel("rust")).toBe("Rust");
    expect(languageLabel("cobol")).toBe("COBOL");
    expect(languageLabel("ts")).toBe("TypeScript");
  });

  it("treats a keyword inside a string as part of the string", () => {
    const html = highlight("const s = 'return';", "ts");
    expect(html).toContain('<span class="tok-string">&#39;return&#39;</span>');
    expect(html).not.toContain('<span class="tok-keyword">return</span>');
  });

  it("treats a whole word only, so information is not in", () => {
    const html = highlight("information", "ts");
    expect(html).toBe("information");
  });

  it("round-trips the source exactly when spans are stripped", () => {
    const source = "def go(n):\n    # count\n    return n * 2  # done\n";
    const stripped = highlight(source, "python")
      .replace(/<\/?span[^>]*>/g, "")
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'");
    expect(stripped).toBe(source);
  });

  it("falls back to plain text rather than scanning an enormous paste", () => {
    const huge = "const x = 1;\n".repeat(20_000);
    expect(highlight(huge, "ts")).not.toContain("<span");
  });

  it("highlights every shipped grammar without throwing", () => {
    for (const language of [
      "bash", "js", "ts", "html", "python", "json", "css", "yaml", "sql", "diff",
    ]) {
      expect(() => highlight("a 'b' 1 # c\n-x\n+y\n", language)).not.toThrow();
    }
  });
});

// B13 — the file viewer has no fence to read a language off, only a name.
describe("languageForFilename", () => {
  it("reads a language off an extension the highlighter ships", () => {
    expect(languageForFilename("src/main.py")).toBe("py");
    expect(languageForFilename("apps/web/src/lib/api.ts")).toBe("ts");
    expect(languageForFilename("STYLE.CSS")).toBe("css");
  });

  it("keeps a language it only labels, so the header still names the file", () => {
    expect(languageForFilename("main.go")).toBe("go");
    expect(languageForFilename("notes.md")).toBe("md");
  });

  it("reads the whole name where the name is the language", () => {
    expect(languageForFilename("Dockerfile")).toBe("dockerfile");
    expect(languageForFilename("Makefile")).toBe("makefile");
  });

  it("refuses to guess rather than making a wrong claim about a file", () => {
    // A prefix match would call this a Dockerfile, which it is not.
    expect(languageForFilename("Dockerfile.bak")).toBe("");
    expect(languageForFilename("LICENSE")).toBe("");
    expect(languageForFilename("archive.")).toBe("");
    expect(languageForFilename("")).toBe("");
  });
});
