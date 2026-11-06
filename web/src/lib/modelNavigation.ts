/** Shared model destinations: the rendered UI and its live catalogue use these. */
export const MODEL_ADD_SOURCES = [
  {
    id: "local",
    name: "On this computer",
    category: "Source",
    description: "A model this machine runs itself. Nothing you send leaves it.",
  },
  {
    id: "account",
    name: "An account I have",
    category: "Source",
    description: "Anthropic, OpenAI, Gemini or another provider, with your own key.",
  },
  {
    id: "huggingface",
    name: "Hugging Face",
    category: "Source",
    description: "Download an open model and run it on this computer.",
  },
  {
    id: "custom",
    name: "Custom endpoint",
    category: "Source",
    description: "A router such as OpenRouter, or a vLLM or home-lab server you control.",
  },
];


export const MODEL_SETTINGS_PANELS = [
  { id: "serving", label: "Running models" },
  { id: "library", label: "Library" },
  { id: "activity", label: "Activity" },
  { id: "advanced", label: "Advanced" },
];
