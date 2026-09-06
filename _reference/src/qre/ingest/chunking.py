import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


@dataclass
class Chunk:
    heading: str | None
    content: str
    ordinal: int


def _split_sections(markdown: str) -> list[tuple[str | None, str]]:
    matches = list(HEADING_RE.finditer(markdown))
    if not matches:
        return [(None, markdown.strip())]

    sections: list[tuple[str | None, str]] = []
    preamble = markdown[: matches[0].start()].strip()
    if preamble:
        sections.append((None, preamble))

    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[match.end() : end].strip()
        if body:
            sections.append((match.group(2).strip(), body))
    return sections


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    parts: list[str] = []
    current = ""

    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chars:
            parts.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{para}".strip() if tail else para
        else:
            current = f"{current}\n\n{para}".strip() if current else para

    if current:
        parts.append(current)
    return parts


def chunk_markdown(markdown: str, *, max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    chunks: list[Chunk] = []
    for heading, body in _split_sections(markdown):
        for part in _split_long(body, max_chars, overlap):
            chunks.append(Chunk(heading=heading, content=part, ordinal=len(chunks)))
    return chunks
