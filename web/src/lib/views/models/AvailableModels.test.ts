import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import AvailableModels from "./AvailableModels.svelte";

afterEach(() => vi.restoreAllMocks());

const CATALOGUE = [
  "anthropic/claude-opus-4-5",
  "anthropic/claude-haiku-4-5",
  "openai/gpt-4o",
  "text-embedding-3-large",
];

function mount(props: Record<string, unknown> = {}) {
  return render(AvailableModels, {
    props: { profileId: "openrouter", catalogue: CATALOGUE, chosen: [], ...props },
  });
}

it("shows a search box that is actually visible", () => {
  // BUG-260 — the search existed in the DOM and could be typed into, and was
  // invisible on screen: a bare `input` rule meant for the switch's hidden
  // checkbox also matched it, at 26px wide and zero opacity. Asserting the
  // element exists would have passed throughout, which is why this asserts the
  // rule that hid it does not apply.
  const { container } = mount();
  const search = container.querySelector<HTMLInputElement>('input[type="search"]');
  expect(search).not.toBeNull();
  expect(search).toBeVisible();
  const hidden = container.querySelector<HTMLInputElement>('input[type="checkbox"]');
  expect(hidden).not.toBeNull();
  // The two inputs must not share styling: one is a control, one is a hitbox.
  expect(search!.className).toContain("search");
  expect(hidden!.className).not.toContain("search");
});

it("narrows the list by name or by identifier", async () => {
  const { container } = mount();
  const search = container.querySelector<HTMLInputElement>('input[type="search"]')!;

  await fireEvent.input(search, { target: { value: "haiku" } });
  expect(container.querySelectorAll(".name")).toHaveLength(1);

  // The raw id works too, so an owner reading a model page can paste from it.
  await fireEvent.input(search, { target: { value: "openai/" } });
  expect(container.querySelectorAll(".name")).toHaveLength(1);

  await fireEvent.input(search, { target: { value: "nothing-like-this" } });
  expect(screen.getByText(/No model matches/)).toBeInTheDocument();
});

it("leaves out what cannot answer a turn, and says how many", () => {
  const { container } = mount();
  expect(container.querySelectorAll(".name")).toHaveLength(3);
  expect(container.querySelector(".count")?.textContent).toContain("1 not chat model");
});

it("marks the current default instead of offering to set it again", () => {
  mount({ defaultModel: "openai/gpt-4o", onuse: vi.fn() });
  expect(screen.getByText("Default")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Use" })).toHaveLength(2);
});

it("hands one model back as the new default", async () => {
  const onuse = vi.fn();
  mount({ onuse });
  await fireEvent.click(screen.getAllByRole("button", { name: "Use" })[0]);
  expect(onuse).toHaveBeenCalledWith("anthropic/claude-opus-4-5");
});

it("keeps a model the owner already chose, whatever it is", () => {
  // An owner's own past choice outranks the chat-model rule.
  const { container } = mount({ chosen: ["text-embedding-3-large"] });
  expect(container.querySelectorAll(".name")).toHaveLength(4);
});

it("saves the switch the owner moved", async () => {
  const save = vi
    .spyOn(api, "setAvailableModels")
    .mockResolvedValue({ profile_id: "openrouter", models: ["openai/gpt-4o"] } as never);
  mount();
  await fireEvent.click(screen.getByRole("checkbox", { name: "GPT-4o" }));
  expect(save).toHaveBeenCalledWith("openrouter", ["openai/gpt-4o"]);
});
