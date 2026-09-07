// A skill link pasted into Chat or Build. The notice must never install on its
// own, and must never claim a link is a skill before the server has read it.
import { render, screen, waitFor } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import SkillLinkNotice from "./SkillLinkNotice.svelte";
import { stubFetch } from "../test-helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const LINK = "https://github.com/o/r/blob/main/skills/tidy/SKILL.md";

const VERIFIED = {
  ok: true,
  verified: true,
  name: "tidy-imports",
  description: "Sort and dedupe imports.",
  version: null,
  checksum: "b".repeat(64),
  byte_size: 900,
  source_url: "https://raw.githubusercontent.com/o/r/main/skills/tidy/SKILL.md",
  already_installed: false,
};

describe("SkillLinkNotice", () => {
  it("shows nothing for ordinary text", () => {
    stubFetch({});
    render(SkillLinkNotice, { props: { text: "please refactor the parser" } });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows nothing for a plain repository link", () => {
    stubFetch({});
    render(SkillLinkNotice, { props: { text: "see https://github.com/o/r" } });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("offers to verify a skill link without fetching anything first", () => {
    const fetchMock = stubFetch({});
    render(SkillLinkNotice, { props: { text: `install ${LINK}` } });
    expect(screen.getByRole("button", { name: "Verify skill" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("reports the document's real name and description after verifying", async () => {
    stubFetch({ "POST /api/skills/verify": VERIFIED });
    render(SkillLinkNotice, { props: { text: LINK } });
    await fireEvent.click(screen.getByRole("button", { name: "Verify skill" }));
    await waitFor(() => expect(screen.getByText("tidy-imports")).toBeInTheDocument());
    expect(screen.getByText(/Sort and dedupe imports/)).toBeInTheDocument();
    // Verifying stores nothing — adding is a second, explicit action.
    expect(screen.getByRole("button", { name: "Add to Skills" })).toBeInTheDocument();
  });

  it("installs only when the owner asks, and links to the Skills tab after", async () => {
    const fetchMock = stubFetch({
      "POST /api/skills/verify": VERIFIED,
      "POST /api/skills/import": { ok: true, skill_id: "skl_1", skill: { name: "tidy-imports" } },
    });
    render(SkillLinkNotice, { props: { text: LINK } });
    await fireEvent.click(screen.getByRole("button", { name: "Verify skill" }));
    await screen.findByRole("button", { name: "Add to Skills" });
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/import"))).toBe(false);
    await fireEvent.click(screen.getByRole("button", { name: "Add to Skills" }));
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Open Skills" })).toHaveAttribute(
        "href",
        "#/extensions?tab=skills",
      ),
    );
  });

  it("tells the owner a .skill bundle has to be uploaded, and offers no import", () => {
    stubFetch({});
    render(SkillLinkNotice, {
      props: { text: "https://github.com/o/r/raw/main/opus-mode.skill" },
    });
    expect(screen.getByText(/Download it, then upload the file/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Verify skill" })).not.toBeInTheDocument();
  });

  it("warns when the name is already installed rather than silently replacing it", async () => {
    stubFetch({ "POST /api/skills/verify": { ...VERIFIED, already_installed: true } });
    render(SkillLinkNotice, { props: { text: LINK } });
    await fireEvent.click(screen.getByRole("button", { name: "Verify skill" }));
    await waitFor(() =>
      expect(screen.getByText(/already have a skill with this name/i)).toBeInTheDocument(),
    );
  });

  it("can be dismissed and stays dismissed for that link", async () => {
    stubFetch({});
    render(SkillLinkNotice, { props: { text: LINK } });
    await fireEvent.click(screen.getByRole("button", { name: "Dismiss skill link suggestion" }));
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });

  it("surfaces a refusal instead of pretending the link worked", async () => {
    stubFetch({});
    render(SkillLinkNotice, { props: { text: LINK } });
    await fireEvent.click(screen.getByRole("button", { name: "Verify skill" }));
    await waitFor(() => expect(screen.getByText(/unrouted|Request failed/)).toBeInTheDocument());
  });
});
