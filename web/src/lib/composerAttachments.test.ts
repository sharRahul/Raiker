import { beforeEach, describe, expect, it, vi } from "vitest";

const uploadAttachment = vi.fn();
vi.mock("./api", () => ({
  api: { uploadAttachment: (...args: unknown[]) => uploadAttachment(...args) },
  ApiError: class ApiError extends Error {},
}));

const { createAttachmentStore, MAX_ATTACHMENTS } = await import("./composerAttachments.svelte");

function file(name: string, type: string, bytes = 4): File {
  return new File([new Uint8Array(bytes)], name, { type });
}

beforeEach(() => {
  uploadAttachment.mockReset();
  uploadAttachment.mockImplementation(
    ({ filename, media_type }: { filename: string; media_type: string }) =>
      Promise.resolve({ attachment_id: `att_${filename}`, media_type, byte_size: 4 }),
  );
});

describe("files dropped on a composer", () => {
  it("routes each file to the validator its button would have used", async () => {
    const store = createAttachmentStore();
    await store.acceptFiles([file("shot.png", "image/png"), file("spec.md", "text/markdown")]);
    expect(store.items.map((item) => item.kind)).toEqual(["image", "document"]);
    expect(store.error).toBeNull();
  });

  it("names a file it cannot take instead of ignoring it", async () => {
    const store = createAttachmentStore();
    await store.acceptFiles([file("payload.exe", "application/x-msdownload")]);
    expect(store.items).toHaveLength(0);
    expect(store.error).toContain("Only plain-text");
    expect(uploadAttachment).not.toHaveBeenCalled();
  });

  it("says why the rest were left when the drop is over the cap", async () => {
    const store = createAttachmentStore();
    const dropped = Array.from({ length: MAX_ATTACHMENTS + 2 }, (_, i) =>
      file(`n${i}.md`, "text/markdown"),
    );
    await store.acceptFiles(dropped);
    expect(store.items).toHaveLength(MAX_ATTACHMENTS);
    expect(store.error).toContain(String(MAX_ATTACHMENTS));
  });

  it("still refuses an oversized image, the same as the picker does", async () => {
    const store = createAttachmentStore();
    await store.acceptFiles([file("huge.png", "image/png", 5_000_001)]);
    expect(store.items).toHaveLength(0);
    expect(store.error).toContain("too large");
  });
});
