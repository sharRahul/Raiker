/**
 * QUI-A block toolbar — a drawn chart as a PNG the owner can keep.
 *
 * The chart is inline SVG styled by the page's tokens, so a bare copy of the
 * element would lose every colour (they are `var(--chart-n)` in a stylesheet
 * the file does not carry). Each drawn element's computed paint is written
 * onto the copy first; then the copy is rasterised at twice its size on a
 * canvas filled with the page's surface colour. No request leaves the page.
 */

const PAINT = ["fill", "stroke", "stroke-width", "opacity", "font-size", "font-weight", "font-family", "text-anchor"];

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url));
}

/** The SVG with its computed paint inlined, as standalone markup. */
export function standaloneSvg(svg: SVGSVGElement): string {
  const copy = svg.cloneNode(true) as SVGSVGElement;
  const source = [svg, ...svg.querySelectorAll("*")];
  const target = [copy, ...copy.querySelectorAll("*")];
  source.forEach((element, index) => {
    const style = getComputedStyle(element);
    const out = target[index] as SVGElement;
    out.removeAttribute("class");
    out.setAttribute(
      "style",
      PAINT.map((name) => `${name}:${style.getPropertyValue(name)}`).join(";"),
    );
  });
  const box = svg.viewBox.baseVal;
  copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  copy.setAttribute("width", String(box.width));
  copy.setAttribute("height", String(box.height));
  copy.removeAttribute("aria-hidden");
  return new XMLSerializer().serializeToString(copy);
}

export async function chartPng(svg: SVGSVGElement, background: string): Promise<Blob> {
  const box = svg.viewBox.baseVal;
  const scale = 2;
  const image = new Image();
  const url = URL.createObjectURL(new Blob([standaloneSvg(svg)], { type: "image/svg+xml" }));
  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("chart_image_unreadable"));
      image.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = box.width * scale;
    canvas.height = box.height * scale;
    const context = canvas.getContext("2d");
    if (context === null) throw new Error("chart_image_no_canvas");
    context.fillStyle = background;
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("chart_image_empty"))), "image/png"),
    );
  } finally {
    URL.revokeObjectURL(url);
  }
}
