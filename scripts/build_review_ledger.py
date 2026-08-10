#!/usr/bin/env python3
"""Create a review ledger from every scan finding; it never supplies verdicts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def anchor_id(finding: dict[str, object], ordinal: int) -> str:
    document_id = str(finding.get("document_id", "single-input"))
    return ":".join(
        (
            document_id,
            str(finding["rule_id"]),
            str(finding["start"]),
            str(finding["end"]),
            str(ordinal),
        )
    )


def build_rows(scan_result: dict[str, object]) -> list[dict[str, object]]:
    findings = scan_result.get("findings")
    if not isinstance(findings, list):
        raise ValueError("scan result must contain a findings list")
    rows: list[dict[str, object]] = []
    for ordinal, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            raise ValueError("scan finding must be an object")
        rows.append(
            {
                "anchor_id": anchor_id(finding, ordinal),
                "document_id": str(finding.get("document_id", "single-input")),
                "rule_id": str(finding["rule_id"]),
                "start": int(finding["start"]),
                "end": int(finding["end"]),
                "line": int(finding["line"]),
                "column": int(finding["column"]),
                "evidence": str(finding["evidence"]),
                "context": str(finding["context"]),
                "review_method": "unreviewed",
                "verdict": "unreviewed",
                "reason": "",
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", type=Path, required=True, help="scan_style.py JSON 결과")
    parser.add_argument("--output", type=Path, required=True, help="생성할 JSONL review ledger")
    args = parser.parse_args()
    result = json.loads(args.scan.read_text(encoding="utf-8"))
    rows = build_rows(result)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
