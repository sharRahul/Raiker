/**
 * UX-MODEL-01 — the sign-in screen's per-provider facts, out of the Models page.
 *
 * Pure data and one lookup, so it is read by whichever component draws the
 * sign-in dialog and tested without rendering anything.
 */
import { providerName } from "../../format";

// Provider brand metadata for the sign-in screen. Each provider is researched
// and matches its real auth surface:
//   - Anthropic: API key only (docs.anthropic.com — x-api-key, no OAuth)
//   - OpenAI: API key (platform.openai.com — Bearer; account login is for the
//     dashboard, not the API itself)
//   - Gemini: API key (AI Studio) AND Google login (Vertex AI / ADC)
//   - OpenRouter: API key only (openrouter.ai — Bearer)
//   - Hugging Face: access token AND login (HF tokens "used in place of
//     password"; huggingface.co/docs)
//   - Ollama local: no auth; Ollama Cloud: API key
// Raiker stores the credential in its encrypted vault — it does not perform a
// real OAuth redirect (that needs backend client-id/redirect support). The
// "Sign in" button links to the provider's key/token page so the user can
// grab one, then paste it here.
export type AuthMethod = "login" | "apikey";
export interface Brand {
  tint: string;
  headline: string;
  credentialLabel: string;
  hint: string;
  authMethods: AuthMethod[];
  loginUrl?: string;
  loginLabel?: string;
}
export function brand(provider: string): Brand {
  switch (provider) {
    case "anthropic":
      return {
        tint: "#d97757",
        headline: "Connect to Anthropic",
        credentialLabel: "Anthropic API key",
        hint: "Create a key at console.anthropic.com. Anthropic uses API keys only — no email login.",
        authMethods: ["apikey"],
        loginUrl: "https://console.anthropic.com/settings/keys",
        loginLabel: "Get an Anthropic key",
      };
    case "openai":
      // Sign-in here means signing in to the OpenAI *platform* account —
      // Google, Microsoft, and Apple all work — to create an API key, which
      // is then pasted below. It deliberately does not claim to use a ChatGPT
      // subscription: ChatGPT Plus/Pro and the API are separately billed, and
      // no subscription grants a third-party app API access. Saying so here
      // is cheaper than a user discovering it through a 401.
      return {
        tint: "#10a37f",
        headline: "Connect to OpenAI",
        credentialLabel: "OpenAI API key",
        hint: "Sign in to platform.openai.com with Google, Microsoft, Apple, or email, then create an API key and paste it below. API usage is billed separately from a ChatGPT subscription — a Plus or Pro plan does not include API access.",
        authMethods: ["login", "apikey"],
        loginUrl: "https://platform.openai.com/api-keys",
        loginLabel: "Sign in with Google or email",
      };
    case "gemini":
      return {
        tint: "#4285f4",
        headline: "Connect to Google AI",
        credentialLabel: "Gemini API key",
        hint: "Create a key in Google AI Studio. Google also supports sign-in with your Google account via Vertex AI.",
        authMethods: ["login", "apikey"],
        loginUrl: "https://aistudio.google.com/apikey",
        loginLabel: "Sign in with Google",
      };
    case "openrouter":
      return {
        tint: "#6b3fa0",
        headline: "Connect to OpenRouter",
        credentialLabel: "OpenRouter API key",
        hint: "Create a key at openrouter.ai/keys. OpenRouter uses API keys only.",
        authMethods: ["apikey"],
        loginUrl: "https://openrouter.ai/keys",
        loginLabel: "Get an OpenRouter key",
      };
    case "huggingface":
      return {
        tint: "#ff9d00",
        headline: "Connect to Hugging Face",
        credentialLabel: "Hugging Face access token",
        hint: "Create a token at huggingface.co/settings/tokens. You can also sign in with your Hugging Face account.",
        authMethods: ["login", "apikey"],
        loginUrl: "https://huggingface.co/settings/tokens",
        loginLabel: "Sign in to Hugging Face",
      };
    case "ollama-cloud":
      return {
        tint: "#22c55e",
        headline: "Connect to Ollama Cloud",
        credentialLabel: "Ollama Cloud API key",
        hint: "Managed Ollama endpoint key. Create one from your Ollama Cloud account.",
        authMethods: ["apikey"],
      };
    case "openai-compatible":
      return {
        tint: "#0f766e",
        headline: "Connect your endpoint",
        credentialLabel: "API key (optional)",
        hint: "A custom OpenAI-compatible endpoint you control (vLLM, home-lab, etc.).",
        authMethods: ["apikey"],
      };
    default:
      return {
        tint: "#0f766e",
        headline: `Connect to ${providerName(provider)}`,
        credentialLabel: "API key",
        hint: "Your provider key, stored encrypted in this Raiker instance.",
        authMethods: ["apikey"],
      };
  }
}
