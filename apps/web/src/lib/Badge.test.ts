import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import Badge from "./Badge.svelte";
import { BADGES, BADGE_VARIANTS } from "./badges";

describe("Badge", () => {
  it("renders an accessible label for every variant", () => {
    for (const variant of BADGE_VARIANTS) {
      const { unmount } = render(Badge, { props: { variant } });
      expect(screen.getByText(BADGES[variant].label)).toBeInTheDocument();
      unmount();
    }
  });

  it("does not rely on colour alone (shape glyph is present but hidden from AT)", () => {
    const { container } = render(Badge, { props: { variant: "blocked" } });
    const symbol = container.querySelector(".badge-symbol");
    expect(symbol).not.toBeNull();
    expect(symbol).toHaveAttribute("aria-hidden", "true");
    expect(symbol?.textContent?.trim().length).toBeGreaterThan(0);
  });
});
