import { render, screen } from "@testing-library/svelte";
import { expect, it } from "vitest";
import IdentityChip from "./IdentityChip.svelte";

it("names a machine proposer and its state without exposing attestation material", () => {
  render(IdentityChip, {
    identity: {
      principal_id: "principal_turn_agent_1",
      principal_type: "ai_agent",
      display_name: "Raiker agent · turn_1",
      subject: "spiffe://raiker/ws/agent/turn/turn_1",
      turn_id: "turn_1",
      key_id: "mkey_1",
      issued_at: "2026-08-08T12:00:00Z",
      expires_at: "2026-08-08T12:15:00Z",
      state: "inactive",
    },
  });

  expect(screen.getByText("Raiker agent · turn_1")).toBeInTheDocument();
  expect(screen.getByText("Agent · inactive")).toBeInTheDocument();
  expect(screen.queryByText(/spiffe:/)).not.toBeInTheDocument();
});

it("compacts long turn ids while retaining the complete audit identity", () => {
  const turnId = "turn_9ac405e037eb49bdb92f9a03c075a825";
  render(IdentityChip, {
    identity: {
      principal_id: "principal_turn_agent_9ac405e037eb49bdb92f9a03c075a825",
      principal_type: "ai_agent",
      display_name: `Raiker agent · ${turnId}`,
      subject: `spiffe://raiker/ws/agent/turn/${turnId}`,
      turn_id: turnId,
      key_id: "mkey_1",
      issued_at: "2026-08-08T12:00:00Z",
      expires_at: "2026-08-08T12:15:00Z",
      state: "inactive",
    },
  });

  expect(screen.getByText("Raiker agent · turn_9ac40…")).toBeInTheDocument();
  expect(screen.getByTitle("principal_turn_agent_9ac405e037eb49bdb92f9a03c075a825")).toBeInTheDocument();
  expect(screen.queryByText(turnId)).not.toBeInTheDocument();
});
