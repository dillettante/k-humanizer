#!/usr/bin/env python3
"""Verify the scope of review claims against a scan result and a review ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_review_ledger import build_rows


MODES = ("sample", "residual", "exhaustive")
METHODS = {"mechanical", "human", "excluded", "unreviewed"}
VERDICTS = {"preserve", "edit", "ask", "false_positive", "unreviewed"}


def claim_contract(mode: str) -> dict[str, object]:
    contracts = {
        "sample": {
            "claim_scope": "표본 검토",
            "allowed_claims": ["표본에서 확인된 경향", "추가 전수 확인 필요"],
            "forbidden_claims": ["전부", "모두", "매번", "낱낱", "각각"],
        },
        "residual": {
            "claim_scope": "전수 기계·규칙 분류",
            "allowed_claims": ["전수 분류 완료", "전수 문맥 확인은 아님", "잔여 항목은 사람 검토 필요"],
            "forbidden_claims": ["전부 문맥 확인", "모든 용례를 읽음", "매번", "낱낱"],
        },
        "exhaustive": {
            "claim_scope": "전수 문맥 검토",
            "allowed_claims": ["전수 문맥 검토 완료", "각 앵커의 판단 근거는 ledger에 기록됨"],
            "forbidden_claims": [],
        },
    }
    return contracts[mode]


def evaluate(scan_result: dict[str, object], rows: list[dict[str, object]], mode: str) -> dict[str, object]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(MODES)}")
    expected_rows = build_rows(scan_result)
    expected_ids = {str(row["anchor_id"]) for row in expected_rows}
    actual_ids = [str(row.get("anchor_id", "")) for row in rows]
    duplicate_ids = sorted({item for item in actual_ids if actual_ids.count(item) > 1})
    actual_id_set = set(actual_ids)
    missing_ids = sorted(expected_ids - actual_id_set)
    unknown_ids = sorted(actual_id_set - expected_ids)
    invalid_rows: list[str] = []
    by_id = {str(row.get("anchor_id", "")): row for row in rows}
    reviewed = 0
    human_reviewed = 0
    unresolved = 0
    for identifier in sorted(expected_ids & actual_id_set):
        row = by_id[identifier]
        method = str(row.get("review_method", ""))
        verdict = str(row.get("verdict", ""))
        if method not in METHODS:
            invalid_rows.append(f"{identifier}: unknown review_method {method}")
            continue
        if verdict not in VERDICTS:
            invalid_rows.append(f"{identifier}: unknown verdict {verdict}")
            continue
        if method == "unreviewed" or verdict == "unreviewed":
            unresolved += 1
        else:
            reviewed += 1
            if method == "human":
                human_reviewed += 1
    failures: list[str] = []
    if missing_ids:
        failures.append(f"ledger에 없는 앵커 {len(missing_ids)}개")
    if unknown_ids:
        failures.append(f"scan에 없는 ledger 앵커 {len(unknown_ids)}개")
    if duplicate_ids:
        failures.append(f"중복 ledger 앵커 {len(duplicate_ids)}개")
    if invalid_rows:
        failures.extend(invalid_rows)
    if mode == "sample" and expected_rows and not human_reviewed:
        failures.append("표본 검토에는 적어도 하나의 사람 문맥 판정이 필요합니다")
    if mode == "residual" and unresolved:
        failures.append(f"전수 분류에는 미검토 앵커 {unresolved}개가 남아 있습니다")
    if mode == "exhaustive":
        non_human = reviewed - human_reviewed
        if unresolved:
            failures.append(f"전수 문맥 검토에는 미검토 앵커 {unresolved}개가 남아 있습니다")
        if non_human:
            failures.append(f"전수 문맥 검토에는 사람 문맥 판정이 아닌 앵커 {non_human}개가 있습니다")
    contract = claim_contract(mode)
    return {
        "schema_version": "0.1",
        "kind": "review-coverage-verification",
        "status": "통과" if not failures else "보류",
        "mode": mode,
        **contract,
        "anchors_total": len(expected_rows),
        "anchors_reviewed": reviewed,
        "anchors_human_reviewed": human_reviewed,
        "anchors_unresolved": unresolved,
        "failures": failures,
    }


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"ledger line {number} must be an object")
        rows.append(value)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", type=Path, required=True, help="scan_style.py JSON 결과")
    parser.add_argument("--ledger", type=Path, required=True, help="JSONL review ledger")
    parser.add_argument("--mode", choices=MODES, required=True, help="표본·전수 분류·전수 문맥 검토 중 주장 범위")
    parser.add_argument("--output", type=Path, help="JSON 결과 파일; 생략하면 표준 출력")
    args = parser.parse_args()
    result = evaluate(json.loads(args.scan.read_text(encoding="utf-8")), read_jsonl(args.ledger), args.mode)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["status"] == "통과" else 2


if __name__ == "__main__":
    raise SystemExit(main())
