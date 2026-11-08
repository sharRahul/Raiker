/**
 * PL-5 for MCP — where a server came from, said on its row.
 *
 * Raiker's connector catalogue labels its own integrations *Supported* or
 * *Experimental*. An MCP server is not in that catalogue: it was added by the
 * owner, offered by a plugin, or is Raiker's own sample. Calling an owner's
 * server *Experimental* would claim Raiker had a verdict on it, so the label
 * says who it came from instead, the way Claude's connector directory labels a
 * server you add yourself *Custom: not reviewed by Anthropic*, and ChatGPT
 * warns that a custom MCP server has not been reviewed by OpenAI.
 *
 * Nothing here grants anything: every tool a server declares still waits for
 * the owner to accept it, and every call goes through Permissions.
 */
export type McpSource = "raiker_sample" | "plugin" | "owner";

export type McpProvenance = { label: string; detail: string };

export function mcpProvenance(source: McpSource, plugin: string | null = null): McpProvenance {
  switch (source) {
    case "raiker_sample":
      return { label: "Raiker sample", detail: "Shipped with Raiker: echo and ping on this computer only." };
    case "plugin":
      return {
        label: "From a plugin",
        detail: `Offered by ${plugin ? `the ${plugin} plugin` : "a plugin"}. Raiker has not reviewed this server.`,
      };
    default:
      return { label: "Added by you", detail: "Raiker has not reviewed this server. Use servers you trust." };
  }
}
