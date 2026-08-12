#!/usr/bin/env python3
"""Self-contained smoke test for the DOCX format scanner."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from scan_docx_format import scan  # noqa: E402


DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>핵심 요약</w:t></w:r></w:p>
<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>✅ 반드시 기억할 핵심입니다.</w:t></w:r></w:p>
<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>항목 하나</w:t></w:r></w:p>
<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>항목 둘</w:t></w:r></w:p>
<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>항목 셋</w:t></w:r></w:p>
</w:body></w:document>"""


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        document = Path(directory) / "fixture.docx"
        with zipfile.ZipFile(document, "w") as archive:
            archive.writestr("word/document.xml", DOCUMENT_XML)
        result = scan(document)
    kinds = {str(item["kind"]) for item in result["findings"]}
    expected = {"short-heading", "emoji", "body-bold", "list-run"}
    missing = sorted(expected - kinds)
    if missing:
        raise SystemExit(f"missing DOCX format findings: {missing}")
    print({"status": "passed", "finding_count": result["finding_count"], "kinds": sorted(kinds)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
