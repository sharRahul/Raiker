import { render, screen } from "@testing-library/svelte";
import { expect, it } from "vitest";
import { makeGate } from "../test-helpers";
import AuthorityMatrix from "./AuthorityMatrix.svelte";

it("separates owner control from the agent's derived authority", () => {
  render(AuthorityMatrix, {
    gates: [
      makeGate({ capability: "shell_execution", state: "enabled_runtime", decision_mode: "ask" }),
      makeGate({ capability: "process_execution", state: "disabled", decision_mode: "allow" }),
      makeGate({ capability: "web_fetch", state: "enabled_runtime", decision_mode: "allow", readiness: { provider_ready: false } }),
    ],
  });

  expect(screen.getByRole("columnheader", { name: "Owner control" })).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "Raiker agent" })).toBeInTheDocument();
  expect(screen.getByText("Ask")).toBeInTheDocument();
  expect(screen.getAllByText("Unavailable")).toHaveLength(2);
  expect(screen.getByText("Not ready")).toBeInTheDocument();
});
