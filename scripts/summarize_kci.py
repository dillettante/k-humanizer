#!/usr/bin/env python3
"""비공개 KCI 수집 결과에서 집계 수준의 품질 통계를 만든다."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR.parent / "evidence" / "private" / "kci"
DEFAULT_OUTPUT = DEFAULT_INPUT / "collection-summary.json"

TOPIC_SIGNALS = {
    "ai_and_llm": ["인공지능", "생성형", "대규모 언어", "llm", "챗gpt", "chatgpt", "기계 생성"],
    "translation_and_post_editing": ["번역", "통역", "포스트에디팅", "post-edit", "translationese"],
    "korean_english_direction": ["한국어", "한영", "영한", "영어", "korean", "english"],
    "style_and_naturalness": ["문체", "자연성", "유창성", "가독성", "명사화", "피동", "종결어미", "대명사"],
    "quality_and_evaluation": ["품질", "정확성", "평가", "오역", "누락"],
}


def record_text(record: dict) -> str:
    parts = []
    for title in record.get("titles", []):
        parts.append(title.get("value", ""))
    for abstract in record.get("abstracts", []):
        parts.append(abstract.get("value", ""))
    return " ".join(parts).casefold()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    runs = []
    unique: dict[str, dict] = {}
    for records_file in sorted(args.input_root.glob("*/records.jsonl")):
        run_id = records_file.parent.name
        records = [json.loads(line) for line in records_file.read_text(encoding="utf-8").splitlines() if line]
        runs.append({"run_id": run_id, "records_before_cross_run_deduplication": len(records)})
        for record in records:
            key = record.get("article_id") or record.get("source_id")
            if key:
                unique.setdefault(str(key), record)

    records = list(unique.values())
    years = Counter(record.get("journal", {}).get("year") for record in records if record.get("journal", {}).get("year"))
    title_languages = Counter(title.get("attributes", {}).get("lang", "unknown") for record in records for title in record.get("titles", []))
    abstract_languages = Counter(item.get("attributes", {}).get("lang", "unknown") for record in records for item in record.get("abstracts", []))
    topic_counts = {label: sum(any(signal in record_text(record) for signal in signals) for record in records) for label, signals in TOPIC_SIGNALS.items()}

    summary = {
        "schema_version": "1.0",
        "scope": "aggregate-only; no paper titles, abstracts, authors, or credentials",
        "runs": runs,
        "records_unique_across_runs": len(records),
        "year_range": [min(years), max(years)] if years else None,
        "records_by_year": dict(sorted(years.items())),
        "title_language_values": dict(sorted(title_languages.items())),
        "abstract_language_values": dict(sorted(abstract_languages.items())),
        "coverage": {
            "has_original_title": sum(any(item.get("attributes", {}).get("lang") == "original" for item in record.get("titles", [])) for record in records),
            "has_original_abstract": sum(any(item.get("attributes", {}).get("lang") == "original" for item in record.get("abstracts", [])) for record in records),
            "has_english_abstract": sum(any(item.get("attributes", {}).get("lang") == "english" for item in record.get("abstracts", [])) for record in records),
            "has_persistent_identifier": sum(bool(record.get("doi") or record.get("uci")) for record in records),
        },
        "topic_signal_counts": topic_counts,
        "caveat": "Topic signals are screening aids, not evidence of a paper's finding or methodological quality.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records_unique_across_runs": len(records), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
