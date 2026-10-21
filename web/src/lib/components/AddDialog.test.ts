import { render, screen } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { describe, expect, it, vi } from "vitest";
import AddDialogHarness from "./AddDialogHarness.test.svelte";

describe("AddDialog (QUI-L04)", () => {
  it("opens on search, categories and one card per option", () => {
    render(AddDialogHarness);
    expect(screen.getByRole("heading", { name: "Add connection" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Search services" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Categories" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Gmail|Slack|GitHub/ })).toHaveLength(3);
  });

  it("filters by search and by category", async () => {
    render(AddDialogHarness);
    await fireEvent.input(screen.getByRole("searchbox"), { target: { value: "email" } });
    expect(screen.getByRole("button", { name: /Gmail/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Slack/ })).not.toBeInTheDocument();
    await fireEvent.input(screen.getByRole("searchbox"), { target: { value: "" } });
    await fireEvent.click(screen.getByRole("button", { name: "Code" }));
    expect(screen.getByRole("button", { name: /GitHub/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Gmail/ })).not.toBeInTheDocument();
  });

  it("shows only the chosen option's steps, with a way back", async () => {
    render(AddDialogHarness);
    await fireEvent.click(screen.getByRole("button", { name: /Slack/ }));
    expect(screen.getByText("Steps for Slack")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Slack" })).toBeInTheDocument();
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
  });

  it("closes from its close button", async () => {
    const onclose = vi.fn();
    render(AddDialogHarness, { props: { onclose } });
    await fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onclose).toHaveBeenCalledTimes(1);
  });
});
