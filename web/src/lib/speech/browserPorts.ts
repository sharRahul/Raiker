/**
 * The conversation's ports in a real browser: the microphone, Silero VAD on
 * Raiker's own copy of onnxruntime's WebAssembly, the managed Whisper engine
 * (through dictation's route), the installed speaking engine, and the speaker.
 */
import wasmUrl from "onnxruntime-web/ort-wasm-simd-threaded.wasm?url";
import { api } from "../api";
import { assetUrl, startCapture, wavFromSamples } from "./capture";
import type { ConversationPorts, TurnHandle } from "./conversation.svelte";
import { browserAudioPort } from "./playbackQueue";
import { SileroVad } from "./vad";

export function browserConversationPorts(
  send: (text: string, onText: (answerSoFar: string) => void) => TurnHandle,
  language?: string,
): ConversationPorts {
  return {
    startCapture: (onFrame) => startCapture({ onFrame }),
    // Nothing is fetched from a CDN: the model and the runtime's WebAssembly
    // are both served by this Raiker.
    loadVad: () => SileroVad.load(assetUrl("voice/silero_vad.onnx"), { wasmPaths: { wasm: wasmUrl } }),
    transcribe: async (utterance) => (await api.transcribeSpeech(wavFromSamples(utterance), language)).text,
    send,
    synthesise: (sentence) => api.speakVoice(sentence),
    audio: browserAudioPort(),
  };
}
