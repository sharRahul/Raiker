# Building an MCP server in Node / TypeScript (MCP SDK)

Read this when implementing in TypeScript. The tool-design decisions in
`SKILL.md` step 2 come first — this file only covers how to express them.

## Install and layout

```
npm install @modelcontextprotocol/sdk zod
```

```
acme-mcp/
├── package.json         "type": "module", bin entry pointing at dist/server.js
├── tsconfig.json
└── src/
    ├── server.ts        McpServer instance + tool registrations
    └── client.ts        fetch calls to the upstream API
```

Keeping the upstream calls in their own module is what lets you test the API
layer without standing up a transport.

## A tool, annotated

```ts
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// Fail at startup rather than on the fortieth tool call.
const API_TOKEN = process.env.ACME_API_TOKEN;
if (!API_TOKEN) {
  console.error("ACME_API_TOKEN is not set. Add it to the server's env block.");
  process.exit(1);
}

const server = new McpServer({ name: "acme", version: "1.0.0" });

server.tool(
  "search_issues",
  // The description is the only documentation the agent reads. Say when to use
  // it, when not to, and what comes back.
  "Search Acme issues by full-text query. Use this to find issues by words in " +
    "the title or body; to fetch an issue you already have the id for, use " +
    "get_issue instead. Returns at most `limit` matches, newest first, each " +
    "with id, title, state, and updated_at, plus a cursor for paging.",
  {
    query: z.string().describe("Words to match in the title or body"),
    state: z.enum(["open", "closed", "all"]).default("open"),
    limit: z.number().int().min(1).max(100).default(20),
  },
  async ({ query, state, limit }) => {
    const controller = new AbortController();
    // A hung tool hangs the whole turn; always bound it.
    const timer = setTimeout(() => controller.abort(), 20_000);
    try {
      const url = new URL("https://api.acme.example/issues");
      url.searchParams.set("q", query);
      url.searchParams.set("state", state);
      url.searchParams.set("per_page", String(limit));
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${API_TOKEN}` },
        signal: controller.signal,
      });
      if (response.status === 404) {
        return {
          isError: true,
          content: [
            {
              type: "text",
              // An error the caller can act on, not a status code to interpret.
              text: "no such project — call list_projects to see valid ids",
            },
          ],
        };
      }
      const payload = await response.json();
      // Project onto the fields a follow-up call needs. Passing the upstream
      // object straight through is how a response eats the context window.
      const issues = payload.items.map(
        (item: Record<string, unknown>) => ({
          id: item.id,
          title: item.title,
          state: item.state,
          updated_at: item.updated_at,
        }),
      );
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ issues, cursor: payload.next_cursor }),
          },
        ],
      };
    } finally {
      clearTimeout(timer);
    }
  },
);

await server.connect(new StdioServerTransport());
```

The Zod schema becomes the input schema, so `z.enum` and `.min()/.max()` are
doing real work — they are constraints the model cannot violate, which is
cheaper than validating and explaining after the fact.

## Errors

Return `{ isError: true, content: [...] }` rather than throwing past the
transport. A thrown exception surfaces to the client as a protocol failure with
no actionable text; an `isError` result reaches the model as something it can
read and recover from on the next turn.

## stdout is the protocol

On stdio, stdout carries the protocol. `console.log` corrupts the session, and
the failure appears client-side as an unrelated parse error. Use `console.error`
for every diagnostic — it goes to stderr, which the client ignores.

This includes anything a dependency prints. If a library logs to stdout, either
configure it otherwise or do not use it in a stdio server.

## Transport

`StdioServerTransport` is the default and what a local client expects. For a
server that must be reachable off-process, use
`StreamableHTTPServerTransport` — but only when something genuinely requires a
network endpoint, since that adds a port, an auth story, and an exposure
decision that stdio does not have.

## Client configuration

What to put in the README so someone can actually run it:

```json
{
  "mcpServers": {
    "acme": {
      "command": "node",
      "args": ["/absolute/path/to/acme-mcp/dist/server.js"],
      "env": { "ACME_API_TOKEN": "..." }
    }
  }
}
```

Absolute paths: the client's working directory is not yours.

## Testing it

```bash
npx @modelcontextprotocol/inspector node dist/server.js
```

The inspector lists the tools and lets you call them by hand — enough to catch a
malformed schema or a description that reads as ambiguous.

Keep a test of the contract the agent actually depends on:

```ts
test("search returns ids usable by get_issue", async () => {
  const result = await searchIssues({ query: "crash on startup", limit: 5 });
  expect(result.issues.length).toBeGreaterThan(0);
  expect(result.issues.every((issue) => issue.id)).toBe(true);
});
```
