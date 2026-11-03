/**
 * Voice spec §5.3/§5.1 — sentences played one after another, stoppable at once.
 *
 * Each sentence is fetched as audio while the one before it plays, so speech
 * runs continuously. `stop()` silences the current sentence immediately and
 * drops everything queued (barge-in, the Stop button, a new answer); a fetch
 * still in flight when it is stopped is discarded when it lands.
 */
export interface AudioPort {
  /** Plays one clip; resolves when it ends. Rejects if it cannot be played. */
  play(clip: Blob): { done: Promise<void>; stop(): void };
}

export interface PlaybackQueue {
  enqueue(sentence: string): void;
  /** Resolves when everything enqueued so far has been spoken (or stopped). */
  drained(): Promise<void>;
  stop(): void;
  readonly speaking: boolean;
}

export function browserAudioPort(): AudioPort {
  return {
    play(clip) {
      const url = URL.createObjectURL(clip);
      const audio = new Audio(url);
      let finish: () => void = () => {};
      const done = new Promise<void>((resolve, reject) => {
        finish = () => {
          URL.revokeObjectURL(url);
          resolve();
        };
        audio.onended = finish;
        audio.onerror = () => {
          URL.revokeObjectURL(url);
          reject(new Error("audio_unplayable"));
        };
      });
      void audio.play().catch(() => finish());
      return {
        done,
        stop() {
          audio.pause();
          finish();
        },
      };
    },
  };
}

export function createPlaybackQueue(
  synthesise: (sentence: string) => Promise<Blob>,
  port: AudioPort,
  hooks: { onSentence?: (sentence: string, index: number) => void; onError?: (error: unknown) => void } = {},
): PlaybackQueue {
  let generation = 0;
  let chain: Promise<void> = Promise.resolve();
  let current: { stop(): void } | null = null;
  let speaking = false;
  let pending = 0;
  let index = 0;

  return {
    get speaking() {
      return speaking;
    },
    enqueue(sentence) {
      const turn = generation;
      const order = index++;
      // Fetch now, play in order: the next sentence synthesises while this one plays.
      const audio = synthesise(sentence);
      pending += 1;
      chain = chain.then(async () => {
        try {
          const clip = await audio;
          if (turn !== generation) return;
          speaking = true;
          hooks.onSentence?.(sentence, order);
          const playing = port.play(clip);
          current = playing;
          await playing.done;
        } catch (error) {
          if (turn === generation) hooks.onError?.(error);
        } finally {
          current = null;
          pending -= 1;
          if (pending === 0) speaking = false;
        }
      });
    },
    drained() {
      return chain;
    },
    stop() {
      generation += 1;
      current?.stop();
      current = null;
      speaking = false;
    },
  };
}
