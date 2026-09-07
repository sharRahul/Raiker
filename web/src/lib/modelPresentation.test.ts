import { describe, expect, it } from "vitest";
import { chatCandidates, imageCandidates, modelName } from "./modelPresentation";

describe("modelName", () => {
  it("turns provider model identifiers into concise product names", () => {
    expect(modelName("gemma4:31b-cloud")).toBe("Gemma 4:31B Cloud");
    expect(modelName("claude-haiku-4-5-20251001")).toBe("Haiku 4.5");
    expect(modelName("claude-opus-4-1-20250805")).toBe("Opus 4.1");
  });

  it.each([
    ["local-gguf", "Local GGUF"],
    ["llama3.2:3b-instruct", "Llama 3.2:3B Instruct"],
    ["mistral-small-3.1-24b-instruct", "Mistral Small 3.1 24B Instruct"],
    ["Qwen/Qwen3-32B", "Qwen 3 32B"],
    ["anthropic/claude-sonnet-4-5-20250929", "Sonnet 4.5"],
    ["meta-llama/Llama-3.3-70B-Instruct", "Llama 3.3 70B Instruct"],
    ["gpt-4o-mini", "GPT-4o Mini"],
    ["gemini-2.5-pro-preview-06-05", "Gemini 2.5 Pro"],
    ["deepseek/deepseek-r1:70b", "DeepSeek R1:70B"],
  ])("formats discovered provider model %s as %s", (identifier, expected) => {
    expect(modelName(identifier)).toBe(expected);
  });

  it("keeps unrecognised identifiers readable without changing them at the API boundary", () => {
    expect(modelName("reasoning-model")).toBe("Reasoning Model");
  });
});

describe("what a provider's catalogue can actually answer with (BUG-258)", () => {
  it("leaves out the endpoint families that cannot serve a turn", () => {
    expect(
      chatCandidates([
        "text-embedding-ada-002",
        "whisper-1",
        "tts-1",
        "dall-e-3",
        "omni-moderation-latest",
        "gpt-4o",
        "o3-mini",
      ]),
    ).toEqual(["gpt-4o", "o3-mini"]);
  });

  it("keeps anything the provider did not name as one of those families", () => {
    // A rule written today must not hide a chat model released tomorrow.
    const models = ["some-new-frontier-model", "meta-llama/Llama-4-70B-Instruct"];
    expect(chatCandidates(models)).toEqual(models);
  });

  it("does not empty a picker it cannot make sense of", () => {
    // A provider whose whole catalogue looks like this is one this rule does
    // not understand; offering too much beats offering nothing.
    const models = ["text-embedding-3-large", "text-embedding-3-small"];
    expect(chatCandidates(models)).toEqual(models);
  });
});

describe("models that draw rather than talk", () => {
  it("offers exactly the image models a catalogue contains", () => {
    expect(
      imageCandidates([
        "gpt-4o",
        "gpt-image-1",
        "dall-e-3",
        "gemini-2.5-flash-image",
        "imagen-3.0-generate-002",
        "claude-sonnet-4-5",
      ]),
    ).toEqual(["gpt-image-1", "dall-e-3", "gemini-2.5-flash-image", "imagen-3.0-generate-002"]);
  });

  it("returns nothing for a provider that draws nothing", () => {
    // Deliberately unlike `chatCandidates`, which falls back to the unfiltered
    // list. A chat picker offering too much is recoverable; a Generate button
    // pointed at a model that cannot draw is not.
    expect(imageCandidates(["claude-sonnet-4-5", "gpt-4o"])).toEqual([]);
  });

  it("keeps image models out of the chat picker", () => {
    // The regression this list exists for: the chat exclusions knew `dall-e`
    // and nothing else, so `gpt-image-1` and `gemini-2.5-flash-image` — the two
    // models Raiker itself declares for images — were both offered as chat
    // models that could never answer a turn.
    expect(chatCandidates(["gpt-4o", "gpt-image-1", "gemini-2.5-flash-image"])).toEqual([
      "gpt-4o",
    ]);
  });
});
