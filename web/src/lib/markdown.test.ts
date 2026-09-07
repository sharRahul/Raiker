import { describe, expect, it } from "vitest";
import { escapeHtml, renderInline, renderMarkdown } from "./markdown";

describe("markdown — block structure", () => {
  it("renders ATX headings at their level", () => {
    expect(renderMarkdown("# Quarterly Report")).toBe("<h1>Quarterly Report</h1>");
    expect(renderMarkdown("### Detail")).toBe("<h3>Detail</h3>");
    expect(renderMarkdown("####### too deep")).toBe("<p>####### too deep</p>");
  });

  it("renders unordered and ordered lists", () => {
    expect(renderMarkdown("- one\n- two")).toBe("<ul><li>one</li><li>two</li></ul>");
    expect(renderMarkdown("1. first\n2. second")).toBe("<ol><li>first</li><li>second</li></ol>");
  });

  it("keeps an ordered list's starting number", () => {
    expect(renderMarkdown("3. third\n4. fourth")).toBe(
      '<ol start="3"><li>third</li><li>fourth</li></ol>',
    );
  });

  it("nests a list inside its parent item", () => {
    expect(renderMarkdown("- outer\n  - inner\n- next")).toBe(
      "<ul><li>outer<ul><li>inner</li></ul></li><li>next</li></ul>",
    );
  });

  it("renders a GFM table with its alignments", () => {
    const html = renderMarkdown("| Metric | Value |\n| --- | ---: |\n| Revenue | 42 |");
    expect(html).toContain("<table>");
    expect(html).toContain("<th>Metric</th>");
    expect(html).toContain('<th class="md-align-right">Value</th>');
    expect(html).toContain('<td class="md-align-right">42</td>');
    expect(html).toContain("<td>Revenue</td>");
  });

  it("leaves a pipe-bearing line alone when there is no delimiter row", () => {
    expect(renderMarkdown("a | b | c")).toBe("<p>a | b | c</p>");
  });

  it("renders a fenced code block with its language label and copy action", () => {
    const html = renderMarkdown("```python\nprint('hi')\n```");
    expect(html).toContain('<div class="md-code" data-lang="python">');
    expect(html).toContain('<span class="md-code-lang">Python</span>');
    // The copy action is a glyph, labelled for anyone who cannot see it.
    expect(html).toContain('class="md-copy" data-md-copy data-copy-state="idle" aria-label="Copy code"');
    expect(html).toContain('<svg class="md-copy-glyph" data-state="idle"');
    expect(html).toContain('<code class="language-python">');
    // The source is still escaped, token by token.
    expect(html).toContain("&#39;hi&#39;");
    expect(html).not.toContain("<script");
  });

  it("labels an unhighlighted block Code rather than dropping the header (BUG-23)", () => {
    const html = renderMarkdown("```\nplain\n```");
    expect(html).toContain('<span class="md-code-lang">Code</span>');
    expect(html).toContain("data-md-copy");
  });

  it("does not apply inline markup inside a code block", () => {
    const html = renderMarkdown("```\n**not bold** and _not italic_\n```");
    expect(html).toContain("**not bold** and _not italic_");
    expect(html).not.toContain("<strong>");
  });

  it("still renders an unterminated fence as code, for streaming output", () => {
    expect(renderMarkdown("```\nhalf a block")).toContain("<code>half a block</code>");
  });

  it("renders blockquotes, recursing into their contents", () => {
    expect(renderMarkdown("> quoted **hard**")).toBe(
      "<blockquote><p>quoted <strong>hard</strong></p></blockquote>",
    );
  });

  it("renders thematic breaks", () => {
    expect(renderMarkdown("---")).toBe("<hr />");
    expect(renderMarkdown("***")).toBe("<hr />");
  });

  it("keeps soft line breaks inside a paragraph", () => {
    expect(renderMarkdown("line one\nline two")).toBe("<p>line one<br />line two</p>");
  });

  it("separates paragraphs on a blank line", () => {
    expect(renderMarkdown("first\n\nsecond")).toBe("<p>first</p><p>second</p>");
  });

  it("closes a paragraph when a block follows without a blank line", () => {
    expect(renderMarkdown("intro:\n- one")).toBe("<p>intro:</p><ul><li>one</li></ul>");
  });

  it("returns nothing for empty or whitespace-only input", () => {
    expect(renderMarkdown("")).toBe("");
    expect(renderMarkdown("   \n\n")).toBe("");
  });

  it("renders plain prose as a single paragraph, unchanged", () => {
    expect(renderMarkdown("Paris is the capital of France.")).toBe(
      "<p>Paris is the capital of France.</p>",
    );
  });
});

describe("markdown — inline", () => {
  it("renders emphasis, strong emphasis and strikethrough", () => {
    expect(renderInline("**bold** _em_ ~~gone~~")).toBe(
      "<strong>bold</strong> <em>em</em> <del>gone</del>",
    );
  });

  it("renders code spans and escapes their contents", () => {
    expect(renderInline("call `<b>run()</b>` now")).toBe(
      "call <code>&lt;b&gt;run()&lt;/b&gt;</code> now",
    );
  });

  it("does not apply emphasis inside a code span", () => {
    expect(renderInline("`a_b_c`")).toBe("<code>a_b_c</code>");
  });

  it("leaves snake_case identifiers alone", () => {
    expect(renderInline("model_request_completed")).toBe("model_request_completed");
  });

  it("leaves an underscore-bearing URL alone", () => {
    expect(renderInline("see https://example.com/a_b_c end")).toBe(
      'see <a href="https://example.com/a_b_c" rel="noopener noreferrer nofollow ugc" ' +
        'target="_blank">https://example.com/a_b_c</a> end',
    );
  });

  it("renders a link with a safe scheme and hardened rel", () => {
    expect(renderInline("[docs](https://example.com/x)")).toBe(
      '<a href="https://example.com/x" rel="noopener noreferrer nofollow ugc" ' +
        'target="_blank">docs</a>',
    );
  });

  it("renders an autolinked bare URL without swallowing trailing punctuation", () => {
    expect(renderInline("go to https://example.com.")).toBe(
      'go to <a href="https://example.com" rel="noopener noreferrer nofollow ugc" ' +
        'target="_blank">https://example.com</a>.',
    );
  });
});

describe("markdown — sanitisation", () => {
  it("escapes every character that could open a tag or attribute", () => {
    expect(escapeHtml(`<a href="x" title='y'>&</a>`)).toBe(
      "&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;",
    );
  });

  it("renders raw HTML in model output as literal text", () => {
    const html = renderMarkdown("<script>alert(1)</script>");
    expect(html).not.toContain("<script");
    expect(html).toBe("<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>");
  });

  it("neutralises an img onerror payload", () => {
    const html = renderMarkdown('<img src=x onerror="alert(1)">');
    expect(html).not.toContain("<img");
    expect(html).not.toContain("onerror=\"");
  });

  it("refuses a javascript: link, keeping the source text visible", () => {
    const html = renderInline("[click](javascript:alert(1))");
    expect(html).not.toContain("<a ");
    expect(html).not.toContain("javascript:alert(1)</a>");
    expect(html).toContain("[click](javascript:alert(1))");
  });

  it("refuses data: and vbscript: links", () => {
    expect(renderInline("[x](data:text/html;base64,PHNjcmlwdD4=)")).not.toContain("<a ");
    expect(renderInline("[x](vbscript:msgbox)")).not.toContain("<a ");
  });

  it("never emits an <img>, so a model cannot trigger a remote fetch", () => {
    const html = renderMarkdown("![pixel](https://tracker.example/p.gif)");
    expect(html).not.toContain("<img");
    expect(html).toContain('class="md-image-link"');
    expect(html).toContain('href="https://tracker.example/p.gif"');
  });

  it("cannot be tricked into emitting an attribute from a code fence language", () => {
    const html = renderMarkdown('```js" onload="alert(1)\nx\n```');
    expect(html).not.toContain("onload");
    expect(html).toContain("<pre><code>x</code></pre>");
  });

  it("escapes quotes inside link text and href", () => {
    const html = renderInline('[a"b](https://example.com/?q="x")');
    // Neither the href nor the label can close its attribute or open a tag.
    expect(html).toContain('href="https://example.com/?q=&quot;x&quot;"');
    expect(html).toContain(">a&quot;b</a>");
  });

  it("cannot have a placeholder forged from characters in the source", () => {
    const forged = `${"\uE000"}0${"\uE001"}\`x\``;
    expect(renderInline(forged)).toBe("0<code>x</code>");
  });

  it("escapes HTML that arrives inside a table cell", () => {
    const html = renderMarkdown("| a | b |\n| --- | --- |\n| <b>x</b> | y |");
    expect(html).toContain("&lt;b&gt;x&lt;/b&gt;");
    expect(html).not.toContain("<b>");
  });
});

// C6 — citation markers become inert chips, and only for ids the turn's source
// ledger actually recorded. The point of the allowlist is that a citation is a
// thing the runtime knows about, never a thing model output can assert.
describe("citation markers", () => {
  const ledger = new Set(["s1", "s2"]);

  it("renders a recorded marker as an inert, labelled button", () => {
    const html = renderMarkdown("Renews in March [s1].", { citations: ledger });
    expect(html).toContain('data-md-cite="s1"');
    expect(html).toContain('class="md-cite"');
    expect(html).toContain('aria-label="Open source 1"');
    // The renderer emits no handler: Markdown.svelte delegates the click.
    expect(html).not.toContain("onclick");
  });

  it("leaves a marker the ledger does not know as the characters it is", () => {
    const html = renderMarkdown("Invented [s9].", { citations: ledger });
    expect(html).not.toContain("md-cite");
    expect(html).toContain("[s9]");
  });

  it("rewrites nothing at all when no ledger is supplied", () => {
    expect(renderMarkdown("Plain [s1].")).not.toContain("md-cite");
  });

  it("does not rewrite a marker inside a code span or a fence", () => {
    const inline = renderMarkdown("The config reads `[s1]` verbatim.", { citations: ledger });
    expect(inline).toContain("<code>[s1]</code>");
    expect(inline).not.toContain("md-cite");
    const fenced = renderMarkdown("```\n[s1]\n```", { citations: ledger });
    expect(fenced).not.toContain("md-cite");
  });

  it("does not leak the allowlist into the next render", () => {
    renderMarkdown("Cited [s1].", { citations: ledger });
    expect(renderMarkdown("Cited [s1].")).not.toContain("md-cite");
  });
});
