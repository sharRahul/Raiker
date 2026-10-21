import { render, screen } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { beforeEach, describe, expect, it } from "vitest";
import ListDetailHarness from "./ListDetailHarness.test.svelte";

const ITEMS = [
  { id: "a", name: "Alpha" },
  { id: "b", name: "Beta" },
  { id: "c", name: "Gamma" },
];

describe("ListDetail (QUI-L02)", () => {
  beforeEach(() => {
    window.location.hash = "#/extensions?tab=services";
  });

  it("hides its search field when the list is empty", () => {
    render(ListDetailHarness, { props: { items: [] } });
    expect(screen.getByText("Nothing here yet.")).toBeInTheDocument();
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("moves the selection with the arrow keys and writes it into the address", async () => {
    render(ListDetailHarness, { props: { items: ITEMS } });
    const list = screen.getByRole("listbox", { name: "Things" });
    await fireEvent.keyDown(list, { key: "ArrowDown" });
    expect(screen.getByRole("heading", { name: "Alpha detail" })).toBeInTheDocument();
    await fireEvent.keyDown(list, { key: "ArrowDown" });
    expect(screen.getByRole("option", { name: "Beta" })).toHaveAttribute("aria-selected", "true");
    expect(window.location.hash).toBe("#/extensions?tab=services&item=b");
    await fireEvent.keyDown(list, { key: "End" });
    expect(screen.getByRole("heading", { name: "Gamma detail" })).toBeInTheDocument();
  });

  it("opens the item a link names", () => {
    window.location.hash = "#/extensions?tab=services&item=c";
    render(ListDetailHarness, { props: { items: ITEMS } });
    expect(screen.getByRole("heading", { name: "Gamma detail" })).toBeInTheDocument();
  });

  it("moves focus into the detail on Enter", async () => {
    render(ListDetailHarness, { props: { items: ITEMS, selectedId: "a" } });
    await fireEvent.keyDown(screen.getByRole("listbox"), { key: "Enter" });
    expect(document.activeElement).toBe(screen.getByRole("region", { name: "Selected item" }));
  });

  it("filters rows with its search field", async () => {
    render(ListDetailHarness, { props: { items: ITEMS } });
    await fireEvent.input(screen.getByRole("searchbox", { name: "Search things" }), {
      target: { value: "gam" },
    });
    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(screen.getByRole("option", { name: "Gamma" })).toBeInTheDocument();
  });

  it("offers a resize handle that clamps the list", async () => {
    render(ListDetailHarness, { props: { items: ITEMS } });
    const handle = screen.getByRole("separator", { name: "Resize the list" });
    await fireEvent.keyDown(handle, { key: "ArrowLeft" });
    expect(Number(handle.getAttribute("aria-valuenow"))).toBeGreaterThanOrEqual(180);
  });
});
