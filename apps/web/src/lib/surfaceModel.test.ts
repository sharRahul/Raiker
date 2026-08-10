// A surface default decides where a picker starts. It is a preference, never
// an authority: the turn still names its exact profile and model, and the
// readiness gate judges that pair.
import { afterEach, describe, expect, it, vi } from "vitest";
import { stubFetch } from "./test-helpers";
import { rememberSurfaceModel, surfaceModel } from "./surfaceModel.svelte";

afterEach(() => vi.unstubAllGlobals());

describe("surface model defaults", () => {
  it("reads only the asked-for surface", async () => {
    stubFetch({
      "GET /api/surface-models": {
        surfaces: {
          chat: { profile_id: "ollama", model: "gemma4:31b-cloud" },
          build: { profile_id: "anthropic-hosted", model: "claude-haiku-4-5" },
        },
      },
    });

    expect(await surfaceModel("chat")).toEqual({
      profileId: "ollama",
      model: "gemma4:31b-cloud",
    });
    expect(await surfaceModel("build")).toEqual({
      profileId: "anthropic-hosted",
      model: "claude-haiku-4-5",
    });
    expect(await surfaceModel("tasks")).toBeNull();
  });

  it("falls back to the global model when the preference cannot be read", async () => {
    stubFetch({});
    expect(await surfaceModel("chat")).toBeNull();
  });

  it("treats a half-stored preference as no preference", async () => {
    stubFetch({
      "GET /api/surface-models": {
        surfaces: { chat: { profile_id: "ollama", model: "" } },
      },
    });
    expect(await surfaceModel("chat")).toBeNull();
  });

  it("persists a complete choice for one surface", async () => {
    const mock = stubFetch({ "PUT /api/surface-models": { ok: true } });

    await rememberSurfaceModel("build", "ollama", "gemma4:31b-cloud");

    const put = mock.mock.calls.find(
      ([, init]) => (init?.method ?? "GET").toUpperCase() === "PUT",
    );
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({
      surface: "build",
      profile_id: "ollama",
      model: "gemma4:31b-cloud",
    });
  });

  it("never writes a partial choice, which would clear the default", async () => {
    const mock = stubFetch({ "PUT /api/surface-models": { ok: true } });

    await rememberSurfaceModel("chat", "ollama", "");
    await rememberSurfaceModel("chat", "", "gemma4:31b-cloud");

    expect(
      mock.mock.calls.some(
        ([, init]) => (init?.method ?? "GET").toUpperCase() === "PUT",
      ),
    ).toBe(false);
  });

  it("does not surface a failed write as an error to the caller", async () => {
    stubFetch({});
    await expect(
      rememberSurfaceModel("chat", "ollama", "gemma4:31b-cloud"),
    ).resolves.toBeUndefined();
  });
});
