# [server name] MCP server

Copy this into the server's `README.md` and fill it in. Everything here exists
because someone tried to run an MCP server and could not: the client config was
missing, the env var name was guessed, or the tool list did not match reality.

## What it does

[One paragraph. What service or capability this exposes, and the kind of task an
agent can accomplish with it. Not a feature list — a sentence someone can use to
decide whether they want it.]

## Requirements

- [runtime and version, e.g. Python 3.11+ / Node 20+]
- [an account, plan, or scope on the upstream service, if one is needed]

## Credentials

| Environment variable | Required | What it is | Where to get it |
|---|---|---|---|
| `SERVICE_API_TOKEN` | yes | Bearer token for the API | [exact page or CLI command] |
| `SERVICE_BASE_URL` | no | Override for self-hosted installs | defaults to `https://api.example.com` |

The server reads these from its environment and fails at startup with a named
message when a required one is missing. Credentials are never tool parameters —
a parameter is something a model can invent and a transcript can capture.

## Install

```bash
[the exact commands, from a clean checkout to a runnable server]
```

## Client configuration

```json
{
  "mcpServers": {
    "[server-name]": {
      "command": "[python | node]",
      "args": ["[absolute path or module]"],
      "env": { "SERVICE_API_TOKEN": "..." }
    }
  }
}
```

Use absolute paths: the client's working directory is not yours.

## Tools

| Tool | Use it for | Returns |
|---|---|---|
| `search_x` | Finding X by words in its title or body | Up to `limit` matches with ids, plus a cursor |
| `get_x` | Fetching one X you already have the id for | The full record |
| `create_x` | [destructive? say so here, in bold] | The created id |

Keep this table in step with the tool descriptions in the code. When they drift,
the descriptions win — those are what the agent reads — but a stale README is
how a human ends up debugging the wrong thing.

## Limits and behaviour worth knowing

- **Pagination**: list tools return at most [N] by default; pass the returned
  cursor as `after` to continue.
- **Rate limits**: [what upstream enforces, and what the server does about it].
- **Timeouts**: every outbound call is bounded at [N] seconds.
- **Destructive operations**: [name them explicitly, or write "none"].

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Client shows the server as failed on start | A required env var is unset — run the command by hand and read stderr |
| Tools never get called | Descriptions are too abstract; say when to use each one |
| Protocol / parse errors mid-session | Something wrote to stdout. On stdio, stdout is the protocol — log to stderr only |
| Responses truncated or context exhausted | A tool is returning the upstream payload verbatim; project onto needed fields |
