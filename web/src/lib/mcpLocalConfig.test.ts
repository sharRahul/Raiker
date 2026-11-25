import { describe, expect, it } from "vitest";
import { argsFromLines, envFromLines, serversFromConfig } from "./mcpLocalConfig";

describe("local MCP server config (MCP-HOST)", () => {
  it("reads a Claude Desktop / Cursor mcpServers block", () => {
    const { servers, skipped } = serversFromConfig(
      JSON.stringify({
        mcpServers: {
          blender: { command: "uvx", args: ["blender-mcp"] },
          playwright: { command: "npx", args: ["-y", "@playwright/mcp@latest"], env: { DEBUG: "1" } },
          remote: { url: "https://example.com/mcp" },
        },
      }),
    );
    expect(servers).toEqual([
      { name: "blender", command: "uvx", args: ["blender-mcp"], env: {} },
      { name: "playwright", command: "npx", args: ["-y", "@playwright/mcp@latest"], env: { DEBUG: "1" } },
    ]);
    expect(skipped).toEqual(["remote"]);
  });

  it("reads a bare map of servers too", () => {
    expect(serversFromConfig('{"x": {"command": "python", "args": ["s.py"]}}').servers[0]!.command).toBe("python");
  });

  it("refuses something that is not an object", () => {
    expect(() => serversFromConfig("[1]")).toThrow(SyntaxError);
  });

  it("takes arguments one per line and variables as NAME=value", () => {
    expect(argsFromLines("-y\n\n @playwright/mcp \n")).toEqual(["-y", "@playwright/mcp"]);
    expect(envFromLines("PORT=9876\nbad line\n1X=2\nTOKEN=a=b")).toEqual({
      env: { PORT: "9876", TOKEN: "a=b" },
      refused: ["bad line", "1X"],
    });
  });
});
