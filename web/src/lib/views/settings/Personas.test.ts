/**
 * ADR-0005 — Settings › Personalisation › Personas.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const listPersonas = vi.fn();
const createPersona = vi.fn();
vi.mock("../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      personas: () => listPersonas(),
      createPersona: (body: unknown) => createPersona(body),
      updatePersona: vi.fn(),
      deletePersona: vi.fn(),
    },
  };
});

import Personas from "./Personas.svelte";

const FAMILIES = [
  { family: "files", label: "Files" },
  { family: "web", label: "Web" },
];

describe("Personas", () => {
  beforeEach(() => {
    listPersonas.mockReset();
    createPersona.mockReset();
    HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) { this.setAttribute("open", ""); };
  });

  it("lists each persona with what it may use", async () => {
    listPersonas.mockResolvedValue({
      families: FAMILIES,
      personas: [{
        persona_id: "persona_1", name: "DataAnalyst", description: "Reads numbers", instructions: "x",
        model_profile: null, model: null, tool_ceiling: ["files"], instructions_sha256: "a",
        created_at: "t", updated_at: "t",
      }],
    });
    render(Personas);
    expect(await screen.findByText("@DataAnalyst")).toBeInTheDocument();
    expect(screen.getByText("Reads numbers")).toBeInTheDocument();
    expect(screen.getByText("Files")).toBeInTheDocument();
  });

  it("adds a persona that keeps only the families chosen", async () => {
    listPersonas.mockResolvedValue({ families: FAMILIES, personas: [] });
    createPersona.mockResolvedValue({});
    render(Personas);
    await fireEvent.click(await screen.findByRole("button", { name: "Add persona" }));
    await fireEvent.input(screen.getByPlaceholderText("DataAnalyst"), { target: { value: "@Copywriter" } });
    await fireEvent.input(screen.getByPlaceholderText(/Lead with the figures/), { target: { value: "Write warmly." } });
    await fireEvent.click(screen.getByLabelText("Only some tools"));
    await fireEvent.click(screen.getByLabelText("Files"));
    await fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(createPersona).toHaveBeenCalled());
    expect(createPersona.mock.calls[0][0]).toMatchObject({
      name: "Copywriter", instructions: "Write warmly.", tool_ceiling: ["web"],
    });
  });

  it("says what failed when the list cannot be read", async () => {
    listPersonas.mockRejectedValue(new Error("down"));
    render(Personas);
    expect(await screen.findByRole("alert")).toHaveTextContent("Your personas could not be read");
  });
});
