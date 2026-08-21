<script lang="ts">
  import type { AudioSessionCoordinator, VoicePlayback } from "../voice";
  import ReadAloudButton from "./ReadAloudButton.svelte";

  let { coordinator, playback }: { coordinator: AudioSessionCoordinator; playback: VoicePlayback } = $props();
</script>

<ReadAloudButton responseId="first" text="One" language="en" {coordinator} {playback} />
<ReadAloudButton responseId="second" text="Two" language="en" {coordinator} {playback} />
