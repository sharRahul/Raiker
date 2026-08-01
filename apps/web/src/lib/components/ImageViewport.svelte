<script lang="ts">
  /**
   * Bounded, client-only image inspection (BUG-26).
   *
   * The inspector could show a picture but not look at it: a screenshot scaled
   * to fit a side column is unreadable, and there was no way to get closer, to
   * move around inside it, or to turn a photo the right way up.
   *
   * Everything here happens in the browser, to pixels the server already sent:
   *
   * * **Nothing is mutated.** Zoom, pan and rotation are a CSS transform on the
   *   `<img>`. The stored artifact is untouched, no re-encode happens, and
   *   closing the pane discards the view — it is a way of looking, not an edit.
   * * **Nothing is fetched.** The `src` is the same session-authorised blob URL
   *   the inspector already resolved. No tile server, no remote image service.
   * * **Every transform is bounded.** Zoom is clamped to a fixed range, and pan
   *   is clamped so the picture can never be dragged out of its own frame and
   *   lost. Rotation is in right angles, so an image is always square to the
   *   viewport.
   * * **It is operable by keyboard.** `+`/`-` zoom, arrows pan, `r` rotates,
   *   `f` fits, `0` resets — announced through the control labels rather than
   *   left as folklore. The frame itself is focusable, so a keyboard user can
   *   reach the picture and not just the buttons around it.
   * * **Motion is a preference.** Transitions are dropped entirely under
   *   `prefers-reduced-motion`; the transform still applies, it just arrives
   *   without animation.
   */
  import Icon from "./Icon.svelte";

  let { src, alt }: { src: string; alt: string } = $props();

  // Bounds. Below `MIN_ZOOM` the picture is a dot; above `MAX_ZOOM` a browser is
  // rasterising far past any real detail. Both ends are deliberately generous
  // for reading small text in a screenshot and still finite.
  const MIN_ZOOM = 0.25;
  const MAX_ZOOM = 8;
  const ZOOM_STEP = 1.25;
  const PAN_STEP = 40;

  let zoom = $state(1);
  let rotation = $state(0);
  let offsetX = $state(0);
  let offsetY = $state(0);
  let frame = $state<HTMLDivElement>();
  let dragging = $state(false);
  let dragOrigin: { x: number; y: number; offsetX: number; offsetY: number } | null = null;

  const zoomPercent = $derived(Math.round(zoom * 100));
  // At or below fit there is nothing to pan to, so the grab cursor would be a
  // lie about what dragging does.
  const pannable = $derived(zoom > 1);
  const untouched = $derived(zoom === 1 && rotation === 0 && offsetX === 0 && offsetY === 0);

  function clamp(value: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, value));
  }

  /**
   * Keep the picture inside its frame.
   *
   * The travel available in each direction is half the overflow the zoom
   * created; past that the image would leave the viewport entirely and the
   * owner would be looking at an empty box with no way back except Reset.
   */
  function clampPan() {
    const box = frame?.getBoundingClientRect();
    const limitX = box ? (box.width * Math.max(zoom - 1, 0)) / 2 : 0;
    const limitY = box ? (box.height * Math.max(zoom - 1, 0)) / 2 : 0;
    offsetX = clamp(offsetX, -limitX, limitX);
    offsetY = clamp(offsetY, -limitY, limitY);
  }

  function setZoom(next: number) {
    zoom = clamp(Number(next.toFixed(3)), MIN_ZOOM, MAX_ZOOM);
    clampPan();
  }

  function zoomIn() { setZoom(zoom * ZOOM_STEP); }
  function zoomOut() { setZoom(zoom / ZOOM_STEP); }
  function rotate() { rotation = (rotation + 90) % 360; }

  /** Back to the whole picture, keeping how it is turned. */
  function fit() {
    zoom = 1;
    offsetX = 0;
    offsetY = 0;
  }

  /** Back to the picture exactly as it arrived. */
  function reset() {
    fit();
    rotation = 0;
  }

  function pan(dx: number, dy: number) {
    offsetX += dx;
    offsetY += dy;
    clampPan();
  }

  function onPointerDown(event: PointerEvent) {
    if (!pannable || event.button !== 0) return;
    dragging = true;
    dragOrigin = { x: event.clientX, y: event.clientY, offsetX, offsetY };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  }

  function onPointerMove(event: PointerEvent) {
    if (!dragging || dragOrigin === null) return;
    offsetX = dragOrigin.offsetX + (event.clientX - dragOrigin.x);
    offsetY = dragOrigin.offsetY + (event.clientY - dragOrigin.y);
    clampPan();
  }

  function endDrag(event: PointerEvent) {
    if (!dragging) return;
    dragging = false;
    dragOrigin = null;
    (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId);
  }

  function onKeydown(event: KeyboardEvent) {
    // Only the keys this surface actually claims. Anything else returns
    // untouched, so Escape still closes the inspector and Tab still moves on.
    switch (event.key) {
      case "+": case "=": zoomIn(); break;
      case "-": case "_": zoomOut(); break;
      case "0": reset(); break;
      case "f": case "F": fit(); break;
      case "r": case "R": rotate(); break;
      case "ArrowLeft": pan(PAN_STEP, 0); break;
      case "ArrowRight": pan(-PAN_STEP, 0); break;
      case "ArrowUp": pan(0, PAN_STEP); break;
      case "ArrowDown": pan(0, -PAN_STEP); break;
      default: return;
    }
    event.preventDefault();
  }
</script>

<div class="image-viewport">
  <div class="controls" role="toolbar" aria-label="Image view">
    <button type="button" class="tool" onclick={zoomOut} disabled={zoom <= MIN_ZOOM} aria-label="Zoom out (minus key)" title="Zoom out (−)">
      <Icon name="zoom-out" size={15} />
    </button>
    <span class="zoom-readout" aria-live="polite">{zoomPercent}%</span>
    <button type="button" class="tool" onclick={zoomIn} disabled={zoom >= MAX_ZOOM} aria-label="Zoom in (plus key)" title="Zoom in (+)">
      <Icon name="zoom-in" size={15} />
    </button>
    <button type="button" class="tool" onclick={fit} aria-label="Fit to pane (F key)" title="Fit to pane (F)">
      <Icon name="fit" size={15} />
    </button>
    <button type="button" class="tool" onclick={rotate} aria-label={`Rotate right (R key), currently ${rotation} degrees`} title="Rotate right (R)">
      <Icon name="rotate" size={15} />
    </button>
    <button type="button" class="tool" onclick={reset} disabled={untouched} aria-label="Reset the view (zero key)" title="Reset (0)">
      Reset
    </button>
  </div>

  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <!-- The frame is genuinely interactive: `role="application"` is the honest
       role, because inside it the arrow keys pan the picture rather than scroll
       the pane. It must therefore be reachable by keyboard, so the tabindex is
       required rather than incidental. -->
  <div
    class="frame"
    class:dragging
    class:pannable
    bind:this={frame}
    role="application"
    aria-label={`${alt} — use plus and minus to zoom, arrow keys to pan, R to rotate`}
    tabindex="0"
    onkeydown={onKeydown}
    onpointerdown={onPointerDown}
    onpointermove={onPointerMove}
    onpointerup={endDrag}
    onpointercancel={endDrag}
  >
    <img
      {src}
      {alt}
      draggable="false"
      style={`transform: translate(${offsetX}px, ${offsetY}px) scale(${zoom}) rotate(${rotation}deg)`}
    />
  </div>
  <p class="hint">Drag to move when zoomed in. Zoom, rotation and position affect this view only — the stored file is unchanged.</p>
</div>

<style>
  .image-viewport { display: grid; gap: var(--space-2); }
  .controls {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    flex-wrap: wrap;
  }
  .tool {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.3rem;
    min-height: 32px;
    min-width: 32px;
    padding: 0 0.45rem;
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    background: var(--surface);
    color: var(--text-2);
    font: inherit;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
  }
  .tool:hover:not(:disabled) { border-color: var(--border-strong); color: var(--text-1); }
  .tool:disabled { opacity: 0.45; cursor: not-allowed; }
  .tool:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
  .zoom-readout {
    min-width: 3.4rem;
    text-align: center;
    color: var(--text-2);
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
  }
  .frame {
    position: relative;
    overflow: hidden;
    display: grid;
    place-items: center;
    height: min(60vh, 34rem);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    /* A chequerboard behind transparency, so a transparent PNG reads as
       transparent instead of blending into the pane. */
    background:
      repeating-conic-gradient(var(--neutral-soft) 0% 25%, transparent 0% 50%) 50% / 16px 16px;
    touch-action: none;
  }
  .frame:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
  .frame.pannable { cursor: grab; }
  .frame.dragging { cursor: grabbing; }
  img {
    max-width: 100%;
    max-height: 100%;
    transform-origin: center center;
    transition: transform 120ms ease;
    user-select: none;
    -webkit-user-drag: none;
  }
  .hint { margin: 0; color: var(--text-3); font-size: 0.72rem; }
  @media (prefers-reduced-motion: reduce) {
    img { transition: none; }
  }
</style>
