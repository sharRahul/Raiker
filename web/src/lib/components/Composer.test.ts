import { fireEvent, render, screen } from "@testing-library/svelte";
import { expect, it } from "vitest";
import ComposerFixture from "./ComposerFixture.svelte";

it("expands the prompt to its content and caps it at 180px", async () => {
  render(ComposerFixture);
  const input = screen.getByLabelText("Prompt") as HTMLTextAreaElement;
  Object.defineProperty(input, "scrollHeight", { configurable: true, value: 120 });
  await fireEvent.input(input, { target: { value: "A longer prompt" } });
  expect(input.style.height).toBe("120px");
  Object.defineProperty(input, "scrollHeight", { configurable: true, value: 240 });
  await fireEvent.input(input, { target: { value: "An even longer prompt" } });
  expect(input.style.height).toBe("180px");
});
