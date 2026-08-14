#!/usr/bin/env python3
"""Check declared strengths and irreducible sequences without scoring prose quality."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REVIEWS = {"preserved", "lost", "ask", "unreviewed"}


def anchor_positions(text: str, anchors: list[str]) -> list[tuple[int, int]] | None:
    if not anchors:
        return None
    cursor = 0
    positions: list[tuple[int, int]] = []
    for anchor in anchors:
        found = text.find(anchor, cursor)
        if found < 0:
            return None
        positions.append((found, found + len(anchor)))
        cursor = found + len(anchor)
    return positions


def anchor_layout(text: str, positions: list[tuple[int, int]] | None) -> dict[str, int] | None:
    if not positions:
        return None
    fragment = text[positions[0][0] : positions[-1][1]]
    paragraphs = [part for part in re.split(r"\n\s*\n", fragment) if part.strip()]
    sentence_marks = re.findall(r"[.!?]+", fragment)
    return {
        "character_span": positions[-1][1] - positions[0][0],
        "paragraphs_spanned": max(1, len(paragraphs)),
        "sentences_spanned": max(1, len(sentence_marks)),
    }


def verify_strength_ledger(
    baseline: str,
    candidate: str,
    ledger: dict[str, Any],
) -> dict[str, object]:
    failures: list[str] = []
    records: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    human_records = 0

    for raw in ledger.get("strengths", []):
        item = dict(raw)
        item_id = str(item.get("id", "")).strip()
        policy = str(item.get("policy", "")).strip()
        baseline_text = str(item.get("baseline_text", ""))
        if not item_id or item_id in seen_ids:
            failures.append(f"invalid or duplicate strength id: {item_id or '<empty>'}")
            continue
        seen_ids.add(item_id)
        required_notes = ("position", "function", "surface_cost", "risk_if_smoothed")
        if any(not str(item.get(field, "")).strip() for field in required_notes):
            failures.append(f"{item_id}: position, function, surface_cost, and risk_if_smoothed are required")
        baseline_found = bool(baseline_text) and baseline_text in baseline
        if not baseline_found:
            failures.append(f"{item_id}: baseline_text not found")

        record: dict[str, object] = {
            "id": item_id,
            "policy": policy,
            "baseline_found": baseline_found,
        }
        if policy == "exact":
            candidate_found = bool(baseline_text) and baseline_text in candidate
            record["candidate_found"] = candidate_found
            if not candidate_found:
                failures.append(f"{item_id}: exact strength missing from candidate")
        elif policy == "functional":
            human_records += 1
            candidate_text = str(item.get("candidate_text", ""))
            review = str(item.get("review", "unreviewed"))
            candidate_found = bool(candidate_text) and candidate_text in candidate
            record.update({"candidate_found": candidate_found, "review": review})
            if not candidate_found:
                failures.append(f"{item_id}: candidate_text not found")
            if review not in REVIEWS:
                failures.append(f"{item_id}: invalid review value")
            if review != "preserved" or not str(item.get("reviewer_note", "")).strip():
                failures.append(f"{item_id}: human preserved decision and reviewer_note required")
        elif policy == "ask":
            human_records += 1
            record["review"] = "ask"
            failures.append(f"{item_id}: author decision required")
        else:
            failures.append(f"{item_id}: policy must be exact, functional, or ask")
        records.append(record)

    sequences: list[dict[str, object]] = []
    for raw in ledger.get("sequences", []):
        item = dict(raw)
        item_id = str(item.get("id", "")).strip()
        if not item_id or item_id in seen_ids:
            failures.append(f"invalid or duplicate sequence id: {item_id or '<empty>'}")
            continue
        seen_ids.add(item_id)
        human_records += 1
        baseline_anchors = [str(value) for value in item.get("baseline_anchors", [])]
        candidate_anchors = [str(value) for value in item.get("candidate_anchors", [])]
        review = str(item.get("review", "unreviewed"))
        baseline_positions = anchor_positions(baseline, baseline_anchors)
        candidate_positions = anchor_positions(candidate, candidate_anchors)
        baseline_ordered = baseline_positions is not None
        candidate_ordered = candidate_positions is not None
        baseline_layout = anchor_layout(baseline, baseline_positions)
        candidate_layout = anchor_layout(candidate, candidate_positions)
        layout_compressed = bool(
            baseline_layout
            and candidate_layout
            and (
                candidate_layout["paragraphs_spanned"] < baseline_layout["paragraphs_spanned"]
                or candidate_layout["sentences_spanned"] < baseline_layout["sentences_spanned"]
            )
        )
        sequence_record: dict[str, object] = {
            "id": item_id,
            "baseline_ordered": baseline_ordered,
            "candidate_ordered": candidate_ordered,
            "baseline_layout": baseline_layout,
            "candidate_layout": candidate_layout,
            "layout_compressed": layout_compressed,
            "review": review,
        }
        sequences.append(sequence_record)
        if not str(item.get("function", "")).strip():
            failures.append(f"{item_id}: function is required")
        if not baseline_ordered:
            failures.append(f"{item_id}: baseline anchors missing or out of order")
        if not candidate_ordered:
            failures.append(f"{item_id}: candidate anchors missing or out of order")
        if review not in REVIEWS:
            failures.append(f"{item_id}: invalid review value")
        if review != "preserved" or not str(item.get("reviewer_note", "")).strip():
            failures.append(f"{item_id}: human preserved decision and reviewer_note required")
        if layout_compressed:
            compression_review = str(item.get("compression_review", "unreviewed"))
            sequence_record["compression_review"] = compression_review
            if compression_review != "preserved" or not str(item.get("compression_note", "")).strip():
                failures.append(f"{item_id}: sequence layout compressed; compression review required")

    if not records and not sequences:
        failures.append("ledger has no strengths or sequences")

    if failures:
        status = "보류"
    elif human_records:
        status = "사람 판정 기록"
    else:
        status = "기계 확인 완료"
    return {
        "schema_version": "0.2",
        "kind": "strength-ledger",
        "status": status,
        "strengths": records,
        "sequences": sequences,
        "failures": failures,
        "requires_human_strength_decision": bool(human_records),
        "limit": "문자열의 존재, 앵커 순서, 문단·문장 분포 축소와 사람이 기록한 판정의 완결성만 확인한다. 단계 사이의 실제 경험·논리와 문학적 성취를 기계가 판정하지 않는다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_strength_ledger(
        args.baseline.read_text(encoding="utf-8"),
        args.candidate.read_text(encoding="utf-8"),
        json.loads(args.ledger.read_text(encoding="utf-8")),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["status"] != "보류" else 2


if __name__ == "__main__":
    raise SystemExit(main())
