// MODEL-09 — the flow says where you are, and cannot drift from the panel.
import { describe, expect, it } from "vitest";
import {
  huggingFaceSteps,
  tokenControlVisible,
  type HuggingFaceProgress,
} from "./huggingFaceSteps";

const START: HuggingFaceProgress = {
  repoSelected: false,
  variantSelected: false,
  previewReady: false,
  downloading: false,
  downloaded: false,
  needsConversion: false,
  converted: false,
};

const active = (progress: HuggingFaceProgress) =>
  huggingFaceSteps(progress).find((step) => step.state === "active")?.id;

const ids = (progress: HuggingFaceProgress) =>
  huggingFaceSteps(progress).map((step) => step.id);

describe("the step rail", () => {
  it("starts on Find model", () => {
    expect(active(START)).toBe("find");
  });

  it("moves to Choose variant once a repository is selected", () => {
    expect(active({ ...START, repoSelected: true })).toBe("variant");
  });

  it("moves to Review download once a variant is chosen", () => {
    expect(active({ ...START, repoSelected: true, variantSelected: true })).toBe("review");
  });

  it("moves to Download while one is running", () => {
    expect(
      active({
        ...START,
        repoSelected: true,
        variantSelected: true,
        previewReady: true,
        downloading: true,
      }),
    ).toBe("download");
  });

  it("ends on Add to My models once the file is on disk", () => {
    expect(active({ ...START, repoSelected: true, downloaded: true })).toBe("add");
  });

  it("marks everything before the current step as done", () => {
    const steps = huggingFaceSteps({ ...START, repoSelected: true, variantSelected: true });
    expect(steps.map((step) => step.state)).toEqual(["done", "done", "active", "ahead", "ahead"]);
  });

  it("goes back when the owner does", () => {
    // The whole reason the rail is derived: a counter kept on the side would
    // still say "Download" while the owner is plainly back in the results list.
    const forward = { ...START, repoSelected: true, variantSelected: true };
    expect(active(forward)).toBe("review");
    expect(active({ ...forward, repoSelected: false, variantSelected: false })).toBe("find");
  });
});

describe("the conversion step", () => {
  it("is absent for a ready-to-run GGUF", () => {
    // A step the flow will never take is a step that makes the flow look longer
    // and more fragile than it is.
    expect(ids(START)).toEqual(["find", "variant", "review", "download", "add"]);
  });

  it("appears only when this variant needs it", () => {
    expect(ids({ ...START, needsConversion: true })).toEqual([
      "find",
      "variant",
      "review",
      "download",
      "convert",
      "add",
    ]);
  });

  it("is where a downloaded Safetensors file waits", () => {
    expect(
      active({ ...START, repoSelected: true, downloaded: true, needsConversion: true }),
    ).toBe("convert");
  });

  it("is passed once the conversion has run", () => {
    expect(
      active({
        ...START,
        repoSelected: true,
        downloaded: true,
        needsConversion: true,
        converted: true,
      }),
    ).toBe("add");
  });
});

describe("the access token control", () => {
  it("is hidden for an ordinary public download", () => {
    // It used to sit beside the search box at equal weight, which told every
    // owner that signing in was a normal part of downloading a public model.
    expect(tokenControlVisible({ selectedRepoGated: false, advancedOpen: false })).toBe(false);
  });

  it("appears when the selected repository is gated", () => {
    expect(tokenControlVisible({ selectedRepoGated: true, advancedOpen: false })).toBe(true);
  });

  it("stays reachable under Advanced for someone who came looking", () => {
    expect(tokenControlVisible({ selectedRepoGated: false, advancedOpen: true })).toBe(true);
  });
});
