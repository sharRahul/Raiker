import { fireEvent, render, screen } from "@testing-library/svelte";
import { expect, it } from "vitest";
import ComposerFixture from "./ComposerFixture.svelte";

it("expands the prompt to its content and caps it at about twelve lines (432px)", async () => {
  render(ComposerFixture);
  const input = screen.getByLabelText("Prompt") as HTMLTextAreaElement;
  Object.defineProperty(input, "scrollHeight", { configurable: true, value: 240 });
  await fireEvent.input(input, { target: { value: "A longer prompt" } });
  expect(input.style.height).toBe("240px");
  Object.defineProperty(input, "scrollHeight", { configurable: true, value: 900 });
  await fireEvent.input(input, { target: { value: "An even longer prompt" } });
  expect(input.style.height).toBe("432px");
  expect(input.style.maxHeight).toBe("432px");
});

it("says what a drop adds inside a visible zone", () => {
  render(ComposerFixture, { dropActive: true });
  expect(screen.getByRole("status")).toHaveTextContent("Drop documents, data files or images here to add them as context");
});

it("turns amber and says why when the context guardrail is set", () => {
  render(ComposerFixture, { contextWarning: "Input exceeds 80% of the model's context window." });
  expect(screen.getByRole("group")).toHaveClass("context-warn");
  expect(screen.getByRole("status")).toHaveTextContent("exceeds 80%");
});
