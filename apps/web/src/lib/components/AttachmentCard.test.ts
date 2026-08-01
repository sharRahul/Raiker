// An attached file has to look like the file it is. A picture shows the
// picture; anything else states what it is and how big, because those are the
// two facts a person checks before sending something. The old presentation —
// one grey pill with a generic paper icon — could tell you neither.
import { render, screen } from "@testing-library/svelte";
import { fireEvent } from "@testing-library/dom";
import { describe, expect, it, vi } from "vitest";
import AttachmentCard from "./AttachmentCard.svelte";
import type { ComposerAttachment } from "../composerAttachments.svelte";

function attachment(overrides: Partial<ComposerAttachment> = {}): ComposerAttachment {
  return {
    kind: "document",
    label: "quarterly-report.pdf",
    detail: "quarterly-report.pdf (application/pdf, 156473 bytes)",
    attachmentId: "att_1",
    mediaType: "application/pdf",
    byteSize: 156_473,
    ...overrides,
  };
}

describe("AttachmentCard", () => {
  it("states a document's type and size, not just its name", async () => {
    render(AttachmentCard, { props: { attachment: attachment() } });
    expect(await screen.findByText("quarterly-report.pdf")).toBeInTheDocument();
    expect(screen.getByText("PDF · 153 KB")).toBeInTheDocument();
  });

  it("shows a picture as the picture, from the local file it was picked from", async () => {
    render(AttachmentCard, {
      props: {
        attachment: attachment({
          kind: "image",
          label: "IMG_7560.jpeg",
          mediaType: "image/jpeg",
          byteSize: 2_218_576,
          previewUrl: "blob:picked",
        }),
      },
    });
    const thumb = document.querySelector("img");
    expect(thumb).not.toBeNull();
    expect(thumb).toHaveAttribute("src", "blob:picked");
    expect(screen.getByText("JPEG · 2.1 MB")).toBeInTheDocument();
  });

  it("prefers a resolved thumbnail for a stored image over nothing", async () => {
    render(AttachmentCard, {
      props: {
        attachment: attachment({ kind: "image", label: "shot.png", mediaType: "image/png" }),
        thumbnail: "blob:stored",
      },
    });
    expect(document.querySelector("img")).toHaveAttribute("src", "blob:stored");
  });

  it("falls back to a type glyph when an image has no thumbnail yet", async () => {
    render(AttachmentCard, {
      props: { attachment: attachment({ kind: "image", label: "shot.png" }) },
    });
    // A missing thumbnail is a worse card, not a broken one — and never a
    // broken-image icon pointing at a URL that could not carry the token.
    expect(document.querySelector("img")).toBeNull();
    expect(await screen.findByText("shot.png")).toBeInTheDocument();
  });

  it("names where a workspace path lives, since that is what identifies it", async () => {
    render(AttachmentCard, {
      props: {
        attachment: {
          kind: "path",
          label: "HANDOFF.md",
          detail: "docs/HANDOFF.md",
          path: "docs/HANDOFF.md",
        },
      },
    });
    expect(await screen.findByText("HANDOFF.md")).toBeInTheDocument();
    expect(screen.getByText("docs/HANDOFF.md")).toBeInTheDocument();
  });

  it("is inert unless it is given something to open", async () => {
    render(AttachmentCard, { props: { attachment: attachment() } });
    await screen.findByText("quarterly-report.pdf");
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("opens and removes through the handlers it is given", async () => {
    const onopen = vi.fn();
    const onremove = vi.fn();
    render(AttachmentCard, { props: { attachment: attachment(), onopen, onremove } });

    await fireEvent.click(await screen.findByRole("button", { name: /open quarterly-report/i }));
    expect(onopen).toHaveBeenCalledTimes(1);

    await fireEvent.click(screen.getByRole("button", { name: /remove attachment/i }));
    expect(onremove).toHaveBeenCalledTimes(1);
  });
});
