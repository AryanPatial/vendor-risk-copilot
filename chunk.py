import re
import sys
from pathlib import Path

MAX_CHARS = 1500
MIN_CHARS = 100
OVERLAP = 150

HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
TABLE_RULE = re.compile(r"^[+|=\-\s]+$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def strip_frontmatter(text):
    title = None
    first_line = text.split("\n", 1)[0]
    if first_line.startswith("name:"):
        title = first_line[len("name:"):].strip()

    end = text.find("\n---")
    body = text[end + 4:] if end != -1 else text
    return title, body.strip()


def clean_tables(text):
    """Markdown tables are drawn with +---+ rules that mean nothing to an embedder."""
    lines = []
    for line in text.split("\n"):
        if TABLE_RULE.match(line) and line.strip():
            continue
        if "|" in line:
            line = " ".join(line.replace("|", " ").replace("**", "").split())
        lines.append(line)
    return "\n".join(lines)


def split_sections(body):
    matches = list(HEADING.finditer(body))
    if not matches:
        return [(None, body)]

    sections = []
    preamble = body[: matches[0].start()].strip()
    if preamble:
        sections.append((None, preamble))

    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[match.end():end].strip()
        if text:
            sections.append((match.group(1).strip(), text))
    return sections


def hard_split(text):
    """Last resort for a block with no paragraph breaks, such as a table."""
    pieces = []
    while len(text) > MAX_CHARS:
        window = text[:MAX_CHARS]
        cut = max(window.rfind(". "), window.rfind("\n"), window.rfind(" "))
        if cut < MAX_CHARS // 2:
            cut = MAX_CHARS
        pieces.append(text[:cut].strip())
        text = text[max(0, cut - OVERLAP):].lstrip()
    if text.strip():
        pieces.append(text.strip())
    return pieces


def overlap_tail(text):
    tail = text[-OVERLAP:]
    space = tail.find(" ")
    return tail[space + 1:] if space != -1 else tail


def split_long(text):
    if len(text) <= MAX_CHARS:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > MAX_CHARS:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(hard_split(paragraph))
        elif current and len(current) + len(paragraph) + 2 > MAX_CHARS:
            pieces.append(current)
            current = overlap_tail(current) + "\n\n" + paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip() if current else paragraph

    if current:
        pieces.append(current)
    return pieces


def chunk_document(path):
    title, body = strip_frontmatter(path.read_text())
    title = title or path.stem.replace("-", " ").title()

    chunks = []
    for heading, text in split_sections(clean_tables(body)):
        for piece in split_long(text):
            if len(piece) < MIN_CHARS:
                continue
            chunks.append({
                "heading": f"{title} - {heading}" if heading else title,
                "content": piece,
                "ordinal": len(chunks),
                "source_file": path.name,
            })
    return chunks


def chunk_directory(directory):
    chunks = []
    for path in sorted(Path(directory).glob("*.md")):
        chunks.extend(chunk_document(path))
    return chunks


if __name__ == "__main__":
    target = Path(sys.argv[1])

    if target.is_dir():
        chunks = chunk_directory(target)
        sizes = [len(c["content"]) for c in chunks]
        print(f"{len(chunks)} chunks from {len(list(target.glob('*.md')))} files")
        print(f"sizes: min {min(sizes)}, max {max(sizes)}, average {sum(sizes)//len(sizes)}")
    else:
        for c in chunk_document(target):
            print(f"\n[{c['ordinal']}] {c['heading']}  ({len(c['content'])} chars)")
            print(f"    {c['content'][:150].replace(chr(10), ' ')}...")
