"""A one-page PDF with real text, built by hand for tests (no PDF library needed)."""

from __future__ import annotations


def minimal_pdf(lines: list[str], drawing: str = "") -> bytes:
    """One Letter page showing ``lines`` in Helvetica, with a correct xref table.

    ``drawing`` is raw content-stream operators painted before the text (a
    swatch: ``"0.1 0.4 0.8 rg 72 500 60 60 re f"``).
    """
    content = (drawing + " " if drawing else "") + "BT /F1 18 Tf 72 720 Td " + " ".join(
        f"({line}) Tj 0 -24 Td" for line in lines
    ) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets: list[int] = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out
