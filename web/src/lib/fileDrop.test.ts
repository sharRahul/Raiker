import { describe, expect, it, vi } from "vitest";
import { carriesFiles, createFileDrop } from "./fileDrop.svelte";

/** A DataTransfer stand-in — jsdom's constructor does not accept a file list. */
function transfer(kind: "files" | "text"): DataTransfer {
  return {
    types: kind === "files" ? ["Files"] : ["text/plain"],
    items: [],
    files: kind === "files" ? ({ length: 1, 0: new File(["x"], "x.md") } as unknown as FileList) : ({ length: 0 } as unknown as FileList),
    dropEffect: "none",
  } as unknown as DataTransfer;
}

function event(type: string, data: DataTransfer | null): DragEvent {
  const dragEvent = new Event(type, { bubbles: true, cancelable: true }) as DragEvent;
  Object.defineProperty(dragEvent, "dataTransfer", { value: data });
  return dragEvent;
}

describe("the shared drop target", () => {
  it("highlights while a file is over it and hands the files over on drop", () => {
    const onFiles = vi.fn();
    const drop = createFileDrop({ onFiles });
    expect(drop.over).toBe(false);

    drop.ondragenter(event("dragenter", transfer("files")));
    expect(drop.over).toBe(true);

    drop.ondrop(event("drop", transfer("files")));
    expect(drop.over).toBe(false);
    expect(onFiles).toHaveBeenCalledOnce();
  });

  it("stays highlighted while the pointer crosses its own children", () => {
    const drop = createFileDrop({ onFiles: vi.fn() });
    drop.ondragenter(event("dragenter", transfer("files")));
    // Entering a child fires enter before the parent's leave.
    drop.ondragenter(event("dragenter", transfer("files")));
    drop.ondragleave(event("dragleave", transfer("files")));
    expect(drop.over).toBe(true);
    drop.ondragleave(event("dragleave", transfer("files")));
    expect(drop.over).toBe(false);
  });

  it("must call preventDefault on dragover, or the browser navigates away", () => {
    const drop = createFileDrop({ onFiles: vi.fn() });
    const over = event("dragover", transfer("files"));
    drop.ondragover(over);
    expect(over.defaultPrevented).toBe(true);
  });

  it("ignores a drag that carries no file, so other drop targets still see it", () => {
    const onFiles = vi.fn();
    const drop = createFileDrop({ onFiles });
    const over = event("dragover", transfer("text"));
    drop.ondragenter(event("dragenter", transfer("text")));
    drop.ondragover(over);
    drop.ondrop(event("drop", transfer("text")));
    expect(drop.over).toBe(false);
    expect(over.defaultPrevented).toBe(false);
    expect(onFiles).not.toHaveBeenCalled();
  });

  it("neither highlights nor accepts while it is disabled", () => {
    const onFiles = vi.fn();
    const drop = createFileDrop({ onFiles, enabled: () => false });
    drop.ondragenter(event("dragenter", transfer("files")));
    expect(drop.over).toBe(false);
    drop.ondrop(event("drop", transfer("files")));
    expect(onFiles).not.toHaveBeenCalled();
  });

  it("recognises a file drag from either types or items", () => {
    expect(carriesFiles(null)).toBe(false);
    expect(carriesFiles(transfer("files"))).toBe(true);
    expect(
      carriesFiles({ types: [], items: [{ kind: "file" }] } as unknown as DataTransfer),
    ).toBe(true);
  });
});
