/**
 * Read-aloud on the installed speaking engine, with the system voice behind it.
 *
 * Voice spec V1: once Kokoro or Piper is installed, read-aloud uses it — the
 * same on-device rule as before, a better voice. When no engine is installed
 * (or voice is off) the request is refused with a reason code, and read-aloud
 * falls back to today's `localService`-only system voice. A refusal is
 * remembered for a minute so every click does not ask again.
 */
import { api, ApiError } from "../api";
import { voicePlayback, type VoicePlayback } from "../voice";
import { browserAudioPort, createPlaybackQueue, type AudioPort } from "./playbackQueue";
import { splitSentences } from "./sentences";

const FALLBACK_CODES = new Set([
  "voice_off", "voice_speaking_not_installed", "voice_speaking_system", "voice_kokoro_runtime_missing", "voice_local_only",
]);
const REMEMBER_MS = 60_000;

export function createManagedPlayback(
  fallback: VoicePlayback,
  synthesise: (text: string) => Promise<Blob> = (text) => api.speakVoice(text),
  port: AudioPort | null = typeof Audio === "undefined" ? null : browserAudioPort(),
  now: () => number = () => Date.now(),
): VoicePlayback {
  let refusedUntil = 0;
  let stopCurrent: (() => void) | null = null;
  let generation = 0;

  return {
    supported: () => port !== null || fallback.supported(),
    speak(ownerId, text, language, handlers) {
      stopCurrent?.();
      const turn = ++generation;
      if (port === null || now() < refusedUntil) {
        fallback.speak(ownerId, text, language, handlers);
        stopCurrent = () => fallback.stop();
        return;
      }
      const sentences = splitSentences(text);
      if (sentences.length === 0) {
        handlers.end();
        return;
      }
      let fellBack = false;
      const queue = createPlaybackQueue(synthesise, port, {
        onError(error) {
          if (turn !== generation || fellBack) return;
          queue.stop();
          if (error instanceof ApiError && error.reasonCode && FALLBACK_CODES.has(error.reasonCode)) {
            fellBack = true;
            refusedUntil = now() + REMEMBER_MS;
            fallback.speak(ownerId, text, language, handlers);
            stopCurrent = () => fallback.stop();
            return;
          }
          handlers.error();
        },
      });
      stopCurrent = () => queue.stop();
      for (const sentence of sentences) queue.enqueue(sentence);
      void queue.drained().then(() => {
        if (turn === generation && !fellBack) handlers.end();
      });
    },
    stop() {
      generation += 1;
      stopCurrent?.();
      stopCurrent = null;
    },
  };
}

export const managedPlayback = createManagedPlayback(voicePlayback);
