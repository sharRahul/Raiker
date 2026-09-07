// B13 — the repository, on screen, in Build.
//
// Three properties are worth defending, and each of them is a property the
// explorer would be worse without rather than a rendering detail:
//
//   * **Lazy.** A connected repository can be a whole monorepo, so a tree that
//     walked itself on open would stall Build on a folder nobody asked for.
//   * **It never guesses.** A file that cannot be shown says which reason
//     applies. An empty pane would read as an empty file, which is a different
//     and much more alarming claim.
//   * **Reading leads to asking.** The open file's path goes into the composer
//     as the same `@` mention the completion menu writes, so the two ways of
//     naming a file are indistinguishable to the turn.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setToken } from "../api";
import type { CodeRepoBrowseView, ProjectBrowseEntry } from "../apiTypes";
import { stubFetch } from "../test-helpers";
import CodeExplorer from "./CodeExplorer.svelte";

afterEach(() => {
  setToken(null);
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function file(name: string, partial: Partial<ProjectBrowseEntry> = {}): ProjectBrowseEntry {
  return {
    name,
    relative_path: name,
    is_directory: false,
    size_bytes: 2048,
    media_type: "text/plain",
    index_state: null,
    ...partial,
  };
}

function dir(name: string): ProjectBrowseEntry {
  return {
    name,
    relative_path: name,
    is_directory: true,
    size_bytes: 0,
    media_type: "",
    index_state: null,
  };
}

function browse(
  entries: ProjectBrowseEntry[],
  partial: Partial<CodeRepoBrowseView> = {},
): CodeRepoBrowseView {
  return {
    path: "",
    parent: null,
    entries,
    truncated: false,
    root_kind: "local",
    root_label: "alpha",
    root_missing: false,
    ...partial,
  };
}

const props = { repoId: "repo_1", repoLabel: "alpha", onclose: () => {} };

describe("CodeExplorer", () => {
  it("expands a directory lazily rather than walking the whole tree", async () => {
    const mock = stubFetch({
      "GET /api/code/repos/repo_1/browse": browse([dir("src"), file("README.md")]),
      "GET /api/code/repos/repo_1/browse?path=src": browse([file("main.py")], {
        path: "src",
      }),
    });
    render(CodeExplorer, { props });

    await fireEvent.click(await screen.findByRole("button", { name: "Expand src" }));

    expect(await screen.findByText("main.py")).toBeVisible();
    expect(mock.mock.calls.filter(([u]) => String(u).includes("/browse")).length).toBe(2);
  });

  it("reads a file only when it is opened, and highlights it by its name", async () => {
    stubFetch({
      "GET /api/code/repos/repo_1/browse": browse([file("main.py")]),
      "GET /api/code/repos/repo_1/file?path=main.py": {
        path: "main.py",
        text: "def go():\n    return 1\n",
        truncated: false,
        size_bytes: 24,
        readable: true,
        reason_code: "",
      },
    });
    render(CodeExplorer, { props });

    await fireEvent.click(await screen.findByRole("button", { name: "Read main.py" }));

    // The text is read off the block rather than matched as one node: it is
    // tokenised into spans, which is the point — the assertion is that the file
    // is there *and* highlighted, not that it arrived as a single string.
    const label = await screen.findByText("Python");
    await waitFor(() =>
      expect(document.querySelector("pre.code")?.textContent).toContain("def go():"),
    );
    // The label is the claim that the highlighting is real; an unknown language
    // renders as plain text with no label rather than a wrong one.
    expect(label).toBeVisible();
    expect(document.querySelectorAll("pre.code .tok-keyword").length).toBeGreaterThan(0);
  });

  // B10 — the workspace could show a file and not say that it no longer parses.
  //
  // The third case is the one worth defending hardest: a language this runtime
  // has no parser for must read as *not checked*, never as *no problems*. A
  // clean bill from a check that did not happen is trusted the same as a real
  // one and is wrong.
  it("shows the parse problems in the file it just opened", async () => {
    stubFetch({
      "GET /api/code/repos/repo_1/browse": browse([file("main.py")]),
      "GET /api/code/repos/repo_1/file?path=main.py": {
        path: "main.py",
        text: "def go(:\n",
        truncated: false,
        size_bytes: 9,
        readable: true,
        reason_code: "",
      },
      "GET /api/code/repos/repo_1/diagnostics?path=main.py": {
        path: "main.py",
        checked: true,
        available: true,
        reason_code: "",
        reason: "",
        diagnostics: [
          {
            path: "main.py",
            line: 1,
            column: 8,
            severity: "error",
            message: "invalid syntax.",
            source: "python-ast",
          },
        ],
      },
    });
    render(CodeExplorer, { props });

    await fireEvent.click(await screen.findByRole("button", { name: "Read main.py" }));

    expect(await screen.findByText("invalid syntax.")).toBeVisible();
    expect(screen.getByText("1:8")).toBeVisible();
  });

  it("says a clean file is clean", async () => {
    stubFetch({
      "GET /api/code/repos/repo_1/browse": browse([file("main.py")]),
      "GET /api/code/repos/repo_1/file?path=main.py": {
        path: "main.py",
        text: "x = 1\n",
        truncated: false,
        size_bytes: 6,
        readable: true,
        reason_code: "",
      },
      "GET /api/code/repos/repo_1/diagnostics?path=main.py": {
        path: "main.py",
        checked: true,
        available: true,
        reason_code: "",
        reason: "",
        diagnostics: [],
      },
    });
    render(CodeExplorer, { props });

    await fireEvent.click(await screen.findByRole("button", { name: "Read main.py" }));

    expect(await screen.findByText("No syntax problems.")).toBeVisible();
  });

  it("never reports a language it cannot parse as having no problems", async () => {
    stubFetch({
      "GET /api/code/repos/repo_1/browse": browse([file("ui.ts")]),
      "GET /api/code/repos/repo_1/file?path=ui.ts": {
        path: "ui.ts",
        text: "export const x = 1;\n",
        truncated: false,
        size_bytes: 20,
        readable: true,
        reason_code: "",
      },
      "GET /api/code/repos/repo_1/diagnostics?path=ui.ts": {
        path: "ui.ts",
        checked: false,
        available: true,
        reason_code: "language_not_parseable",
        reason: "No parser for typescript on this runtime.",
        diagnostics: [],
      },
    });
    render(CodeExplorer, { props });

    await fireEvent.click(await screen.findByRole("button", { name: "Read ui.ts" }));

    expect(
      await screen.findByText("Not checked — no parser for this language here."),
    ).toBeVisible();
    expect(screen.queryByText("No syntax problems.")).toBeNull();
  });

  it("still shows the file when the diagnostics read fails", async () => {
    // A repository the owner can read is worth more than a diagnostic.
    stubFetch({
      "GET /api/code/repos/repo_1/browse": browse([file("main.py")]),
      "GET /api/code/repos/repo_1/file?path=main.py": {
        path: "main.py",
        text: "x = 1\n",
        truncated: false,
        size_bytes: 6,
        readable: true,
        reason_code: "",
      },
    });
    render(CodeExplorer, { props });

    await fireEvent.click(await screen.findByRole("button", { name: "Read main.py" }));

    await waitFor(() =>
      expect(document.querySelector("pre.code")?.textContent).toContain("x = 1"),
    );
    expect(screen.queryByText("No syntax problems.")).toBeNull();
  });

  it("says why a file cannot be shown instead of rendering an empty pane", async () => {
    stubFetch({
      "GET /api/code/repos/repo_1/browse": browse([file("logo.png")]),
      "GET /api/code/repos/repo_1/file?path=logo.png": {
        path: "logo.png",
        text: "",
        truncated: false,
        size_bytes: 900,
        readable: false,
        reason_code: "binary_file",
      },
    });
    render(CodeExplorer, { props });

    await fireEvent.click(await screen.findByRole("button", { name: "Read logo.png" }));

    expect(await screen.findByText(/not text/)).toBeVisible();
  });

  it("says a GitHub coordinate has no checkout rather than showing an empty tree", async () => {
    stubFetch({
      "GET /api/code/repos/repo_1/browse": browse([], {
        root_kind: "github",
        root_missing: true,
        reason_code: "repo_not_checked_out",
      }),
    });
    render(CodeExplorer, { props });

    expect(await screen.findByText(/not a checkout/)).toBeVisible();
  });

  it("hands the open file's path to the composer as an @ mention", async () => {
    stubFetch({
      "GET /api/code/repos/repo_1/browse": browse([file("src/main.py", { name: "main.py" })]),
      "GET /api/code/repos/repo_1/file?path=src%2Fmain.py": {
        path: "src/main.py",
        text: "x = 1\n",
        truncated: false,
        size_bytes: 6,
        readable: true,
        reason_code: "",
      },
    });
    const mentioned: string[] = [];
    render(CodeExplorer, {
      props: { ...props, onmention: (path: string) => mentioned.push(path) },
    });

    await fireEvent.click(await screen.findByRole("button", { name: "Read main.py" }));
    await fireEvent.click(
      await screen.findByRole("button", { name: "Mention src/main.py in the composer" }),
    );

    await waitFor(() => expect(mentioned).toEqual(["src/main.py"]));
  });

  it("states a repository it could not read rather than showing nothing", async () => {
    stubFetch({
      "GET /api/code/repos/repo_1/browse": { __status: 500, detail: { reason_code: "boom" } },
    });
    render(CodeExplorer, { props });

    expect(await screen.findByText(/could not be read \(500\)/)).toBeVisible();
  });
});
