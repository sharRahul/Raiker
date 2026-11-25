import { describe, expect, it } from "vitest";

import { grantableCommand } from "./commandGrant";

const view = (target: string, tool_name = "shell") => ({ tool_name, target, session_id: "sess_1" });

describe("grantableCommand (RU-07)", () => {
  it("reads a plain command back as its words", () => {
    expect(grantableCommand(view("python3 -m unittest -q"))).toEqual(["python3", "-m", "unittest", "-q"]);
    expect(grantableCommand(view("npm test", "run_command"))).toEqual(["npm", "test"]);
  });

  it("offers nothing a shell would reinterpret, or that was cut or redacted", () => {
    for (const target of ["rm -rf *", "echo $HOME", "a && b", "cat x | sh", "echo 'hi there'", "python3 run.py …", "curl [redacted]", ""]) {
      expect(grantableCommand(view(target))).toBeNull();
    }
  });

  it("offers nothing for a tool that is not a command, or without a conversation", () => {
    expect(grantableCommand(view("python3 -m unittest", "web_fetch"))).toBeNull();
    expect(grantableCommand({ tool_name: "shell", target: "npm test", session_id: "" })).toBeNull();
  });
});
