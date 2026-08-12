#!/usr/bin/env python3
"""Audit repeated edits for convergence without scoring prose quality."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from measure_edit import measure
from verify_markdown_structure import verify


def audit(
    baseline: str,
    versions: list[tuple[str, str]],
    baseline_id: str = "baseline",
) -> dict[str, object]:
    if not versions:
        raise ValueError("at least one version is required")

    rows: list[dict[str, object]] = []
    previous = baseline
    saw_no_change = False
    changed_after_no_change = False
    seen_hashes = {hashlib.sha256(baseline.encode("utf-8")).hexdigest(): baseline_id}
    oscillations: list[dict[str, str]] = []

    for label, text in versions:
        from_previous = measure(previous, text)
        from_baseline = measure(baseline, text)
        same_as_previous = text == previous
        if saw_no_change and not same_as_previous:
            changed_after_no_change = True
        saw_no_change = saw_no_change or same_as_previous
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if not same_as_previous and text_hash in seen_hashes:
            oscillations.append({"current": label, "returned_to": seen_hashes[text_hash]})
        seen_hashes.setdefault(text_hash, label)
        structure = verify(baseline, text)
        rows.append(
            {
                "label": label,
                "same_as_previous": same_as_previous,
                "changed_character_ratio_from_previous": from_previous["changed_character_ratio"],
                "changed_character_ratio_from_baseline": from_baseline["changed_character_ratio"],
                "changed_sentence_slots_from_previous": from_previous["changed_sentence_slots"],
                "markdown_structure": structure["status"],
                "markdown_changed": structure["changed"],
            }
        )
        previous = text

    format_failures = [row["label"] for row in rows if row["markdown_structure"] != "통과"]
    warnings: list[str] = []
    if changed_after_no_change:
        warnings.append("무수정 회차 뒤 본문이 다시 변경됨—새 edit 근거 확인 필요")
    if oscillations:
        warnings.append("본문이 이전 회차의 동일 상태로 되돌아감—표현 왕복 근거 확인 필요")
    if format_failures:
        warnings.append("baseline 대비 Markdown 구조가 달라짐")

    return {
        "schema_version": "0.1",
        "kind": "iteration-audit",
        "status": "기계 확인 완료" if not warnings else "사람 검토",
        "baseline": {
            "id": baseline_id,
            "sha256": hashlib.sha256(baseline.encode("utf-8")).hexdigest(),
        },
        "versions": rows,
        "oscillations": oscillations,
        "warnings": warnings,
        "latest_same_as_previous": bool(rows[-1]["same_as_previous"]),
        "requires_human_convergence_decision": True,
        "recommendation": "baseline 의미 명세와 회차 대장을 사람이 확인한 뒤 수렴·수정·롤백을 결정",
        "limit": "변경량·무수정·문서 전체의 exact 왕복·Markdown 표지만 확인한다. 문장 일부의 왕복, 수렴, 의미 보존, 자연스러움, AI 작성 여부는 판정하지 않는다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--version", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    baseline = args.baseline.read_text(encoding="utf-8")
    versions = [(str(path.resolve()), path.read_text(encoding="utf-8")) for path in args.version]
    result = audit(baseline, versions, baseline_id=str(args.baseline.resolve()))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["status"] == "기계 확인 완료" else 2


if __name__ == "__main__":
    raise SystemExit(main())
