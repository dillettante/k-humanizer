#!/usr/bin/env python3
"""Report contextual DOCX formatting candidates without modifying the document."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{%s}" % NS["w"]
EMOJI = re.compile("[\\U0001F300-\\U0001FAFF\\u2600-\\u27BF]")


def truthy(element: ET.Element | None) -> bool:
    if element is None:
        return False
    value = element.get(W + "val")
    return value not in {"0", "false", "off", "none"}


def paragraph_record(paragraph: ET.Element, index: int) -> dict[str, object]:
    runs = paragraph.findall("w:r", NS)
    text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS))
    p_style = paragraph.find("w:pPr/w:pStyle", NS)
    style = p_style.get(W + "val", "") if p_style is not None else ""
    numbered = paragraph.find("w:pPr/w:numPr", NS) is not None
    bold_characters = 0
    bold_runs = 0
    for run in runs:
        run_text = "".join(node.text or "" for node in run.findall(".//w:t", NS))
        if truthy(run.find("w:rPr/w:b", NS)):
            bold_runs += 1
            bold_characters += len(run_text.strip())
    visible = max(1, len(text.strip()))
    return {
        "paragraph": index,
        "text": text,
        "style": style,
        "numbered": numbered,
        "bold_runs": bold_runs,
        "bold_ratio": round(bold_characters / visible, 3),
    }


def scan(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    records = [paragraph_record(paragraph, index) for index, paragraph in enumerate(root.findall(".//w:body/w:p", NS), start=1)]
    findings: list[dict[str, object]] = []
    list_run: list[int] = []
    for record in records:
        text = str(record["text"])
        style = str(record["style"])
        heading = style.lower().startswith("heading") or style.startswith("제목")
        for match in EMOJI.finditer(text):
            findings.append({"rule_id": "KH-S10", "kind": "emoji", "paragraph": record["paragraph"], "evidence": match.group(0), "context": text[:120]})
        if not heading and len(text.strip()) >= 8 and float(record["bold_ratio"]) >= 0.6:
            findings.append({"rule_id": "KH-S10", "kind": "body-bold", "paragraph": record["paragraph"], "evidence": f"bold_ratio={record['bold_ratio']}", "context": text[:120]})
        if heading and 0 < len(text.strip()) <= 24:
            findings.append({"rule_id": "KH-S10", "kind": "short-heading", "paragraph": record["paragraph"], "evidence": style, "context": text[:120]})
        if bool(record["numbered"]):
            list_run.append(int(record["paragraph"]))
        else:
            if len(list_run) >= 3:
                findings.append({"rule_id": "KH-S28", "kind": "list-run", "paragraphs": list_run.copy(), "evidence": f"{len(list_run)}개 연속 목록"})
            list_run = []
    if len(list_run) >= 3:
        findings.append({"rule_id": "KH-S28", "kind": "list-run", "paragraphs": list_run.copy(), "evidence": f"{len(list_run)}개 연속 목록"})
    return {
        "schema_version": "0.1",
        "kind": "docx-format-candidate-scan",
        "input": str(path),
        "paragraph_count": len(records),
        "finding_count": len(findings),
        "findings": findings,
        "limit": "서식 후보만 보고한다. 제목·목록·강조의 의미 기능은 장르와 문맥을 읽어 판단한다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = scan(args.input)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
