from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable
from zipfile import ZipFile
import xml.etree.ElementTree as ET


def load_pdf(path: str | Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PDF support requires pypdf to be installed") from exc

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return normalize_text("\n".join(pages))


def load_docx(path: str | Path) -> str:
    docx_path = Path(path)
    with ZipFile(docx_path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [text.text for text in paragraph.findall(".//w:t", namespace) if text.text]
        if texts:
            paragraphs.append("".join(texts))
    return normalize_text("\n".join(paragraphs))


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"-\n(?=\w)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[dict[str, object]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")

    chunks: list[dict[str, object]] = []
    start = 0
    chunk_index = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk_text_value = text[start:end].strip()
        if chunk_text_value:
            chunks.append(
                {
                    "chunk_id": f"C{chunk_index + 1}",
                    "start_char": start,
                    "end_char": end,
                    "text": chunk_text_value,
                }
            )
            chunk_index += 1
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks
