from qre.ingest.chunking import chunk_markdown


def test_splits_on_headings():
    md = "# Title\n\nIntro text.\n\n## Data at Rest\n\nAES-256 everywhere.\n"
    chunks = chunk_markdown(md)
    headings = [c.heading for c in chunks]
    assert "Data at Rest" in headings
    assert all(c.content for c in chunks)


def test_preamble_before_first_heading_is_kept():
    chunks = chunk_markdown("Some loose text.\n\n# Later\n\nBody.")
    assert chunks[0].heading is None
    assert chunks[0].content == "Some loose text."


def test_long_sections_are_split_with_overlap():
    body = "\n\n".join(f"Paragraph number {i} with enough text to matter." * 3 for i in range(20))
    chunks = chunk_markdown(f"# Big\n\n{body}", max_chars=400, overlap=50)
    assert len(chunks) > 1
    assert all(len(c.content) <= 700 for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_document_without_headings():
    chunks = chunk_markdown("Just one paragraph.")
    assert len(chunks) == 1
    assert chunks[0].heading is None
