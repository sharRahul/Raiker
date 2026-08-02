# Building an MCP server in Python (FastMCP)

Read this when implementing in Python. The tool-design decisions in `SKILL.md`
step 2 come first — this file only covers how to express them.

## Install and layout

```
pip install "mcp[cli]"
```

```
acme-mcp/
├── pyproject.toml
├── README.md            how to configure it in a client
└── acme_mcp/
    ├── __init__.py
    ├── server.py        FastMCP instance + tool definitions
    └── client.py        HTTP calls to the upstream API
```

Keeping the upstream calls out of `server.py` matters more than it looks: it is
what lets you test the API layer without a running MCP session.

## A tool, annotated

```python
import os
from typing import Literal

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("acme")

# Fail at import time rather than on the fortieth tool call.
API_TOKEN = os.environ.get("ACME_API_TOKEN")
if not API_TOKEN:
    raise RuntimeError("ACME_API_TOKEN is not set. Add it to the server's env block.")


@mcp.tool()
async def search_issues(
    query: str,
    state: Literal["open", "closed", "all"] = "open",
    limit: int = 20,
) -> dict:
    """Search Acme issues by full-text query.

    Use this to find issues by words in the title or body. To fetch an issue you
    already have the id for, use `get_issue` instead — it is one request and
    returns the full body. Returns at most `limit` matches, newest first, each
    with `id`, `title`, `state`, and `updated_at`; pass the returned `cursor`
    back as `after` to page.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://api.acme.example/issues",
            params={"q": query, "state": state, "per_page": min(limit, 100)},
            headers={"Authorization": f"Bearer {API_TOKEN}"},
        )
    if response.status_code == 404:
        # An error the caller can act on, not a status code it has to interpret.
        return {"error": "no such project — call list_projects to see valid ids"}
    response.raise_for_status()
    payload = response.json()
    # Project onto the fields a follow-up call needs. Returning the upstream
    # object verbatim is how a tool response ends up eating the context window.
    return {
        "issues": [
            {
                "id": item["id"],
                "title": item["title"],
                "state": item["state"],
                "updated_at": item["updated_at"],
            }
            for item in payload["items"]
        ],
        "cursor": payload.get("next_cursor"),
    }
```

Type hints become the input schema, so `Literal[...]` for an enum and a default
for an optional parameter are doing real work — they are the constraints the
model cannot violate.

The docstring becomes the tool description. Write it for an agent that has never
seen the API.

## Transport

```python
if __name__ == "__main__":
    mcp.run()  # stdio — the default, and what a local client expects
```

For a server that must be reachable off-process, use streamable HTTP:

```python
mcp.run(transport="streamable-http")
```

Choose stdio unless something genuinely requires a network endpoint. stdio needs
no port, no auth layer of its own, and no exposure decision.

## stdout is the protocol

On stdio, anything written to stdout is parsed as protocol. A stray `print()`,
a library's progress bar, or a warning printed by a dependency will corrupt the
session, and the failure surfaces on the client as an unrelated parse error.

```python
import logging
import sys

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
```

If a dependency insists on printing, redirect stdout for the duration of the
call with `contextlib.redirect_stdout(sys.stderr)`.

## Resources and prompts

Beyond tools, FastMCP exposes read-only resources and reusable prompts:

```python
@mcp.resource("acme://projects/{project_id}/readme")
def project_readme(project_id: str) -> str:
    """The project's README, for context rather than action."""
    ...
```

Use a resource when the client should be able to *read* something without the
model deciding to call anything. Use a tool when an action or a parameterised
query is involved.

## Client configuration

What to put in the README so someone can actually run it:

```json
{
  "mcpServers": {
    "acme": {
      "command": "python",
      "args": ["-m", "acme_mcp.server"],
      "env": { "ACME_API_TOKEN": "..." }
    }
  }
}
```

## Testing it

```bash
mcp dev acme_mcp/server.py     # inspector UI: list tools, call them by hand
```

Then in-process, without a transport at all:

```python
import pytest

@pytest.mark.asyncio
async def test_search_returns_ids_for_follow_up() -> None:
    result = await search_issues("crash on startup", limit=5)
    assert result["issues"], "search returned nothing for a known query"
    assert all("id" in issue for issue in result["issues"])
```

The second style is the one worth keeping in CI: it tests the contract the agent
depends on — that the response carries what the next call needs.
