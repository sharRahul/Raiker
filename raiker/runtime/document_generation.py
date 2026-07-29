"""Small, deterministic local document generators for Chat artifacts.

The formats are intentionally conservative: Markdown is UTF-8, DOCX/XLSX are
minimal macro-free OOXML packages, and PDF uses built-in Helvetica. No office
suite, browser, template engine, network access, or executable content is used.
"""
from __future__ import annotations

import contextlib
import csv
import io
import os
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from raiker.runtime.attachments import (
    DOCX_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
    StoredAttachment,
    store_document,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import resolve_writable_workspace_path

MEDIA_TYPES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".docx": DOCX_MEDIA_TYPE,
    ".xlsx": XLSX_MEDIA_TYPE,
    ".pdf": PDF_MEDIA_TYPE,
}


def _zip(entries: dict[str, str]) -> bytes:
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content.encode("utf-8"))
    return target.getvalue()


def _docx(text: str) -> bytes:
    paragraphs = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>'
        for line in text.splitlines() or [""]
    )
    return _zip({
        "[Content_Types].xml": '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}<w:sectPr/></w:body></w:document>',
    })


def _column_name(index: int) -> str:
    value = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        value = chr(65 + remainder) + value
    return value


def _xlsx(text: str) -> bytes:
    rows = list(csv.reader(io.StringIO(text)))
    sheet_rows = []
    for row_index, row in enumerate(rows or [[""]], 1):
        cells = "".join(
            f'<c r="{_column_name(column_index)}{row_index}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
            for column_index, value in enumerate(row, 1)
        )
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')
    return _zip({
        "[Content_Types].xml": '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": f'<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>',
    })


def _pdf(text: str) -> bytes:
    lines = [line[:100] for line in (text.splitlines() or [""])][:48]
    commands = ["BT", "/F1 11 Tf", "50 770 Td", "14 TL"]
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.extend([f"({safe}) Tj", "T*"])
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    output.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def generate_document(
    workspace_root: str | Path, store: SQLiteStore, *, path: str, text: str,
    session_id: str, turn_id: str, principal_id: str,
) -> dict[str, object]:
    target = resolve_writable_workspace_path(workspace_root, path)
    suffix = target.suffix.lower()
    media_type = MEDIA_TYPES.get(suffix)
    if media_type is None:
        return {"status": "failed", "error": {"type": "unsupported_document_format"}}
    data = (
        text.encode("utf-8") if suffix in {".md", ".markdown"}
        else _docx(text) if suffix == ".docx"
        else _xlsx(text) if suffix == ".xlsx"
        else _pdf(text)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)
    stored: StoredAttachment = store_document(
        store, filename=target.name, media_type=media_type, data=data,
        owner_principal_id=principal_id,
    )
    store.save_session_attachment_ref(
        session_id=session_id, attachment_id=stored.attachment_id,
        owner_principal_id=principal_id, turn_id=turn_id, source="generated",
    )
    return {
        "status": "success", "path": str(target.relative_to(Path(workspace_root).resolve())),
        "attachment_id": stored.attachment_id, "filename": stored.filename,
        "media_type": stored.media_type, "byte_size": stored.byte_size,
        "artifact_status": "ready",
    }
