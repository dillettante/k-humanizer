#!/usr/bin/env python3
"""Run public deterministic scan and gate fixtures without network access."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scan_style import scan, scan_manifest
from compare_candidates import compare
from verify_style_gate import gate
from build_review_ledger import build_rows
from verify_coverage import evaluate
from audit_term_migration import audit as audit_term_migration


DEFAULT_FIXTURE_DIRS = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures-public",
    Path(__file__).resolve().parent.parent / "tests" / "fixtures-adversarial",
)


def text_at(fixture: Path, name: str) -> str:
    return (fixture.parent / name).read_text(encoding="utf-8")


def run_fixture(fixture: Path) -> dict[str, object]:
    config = json.loads(fixture.read_text(encoding="utf-8"))
    before = text_at(fixture, str(config["before"]))
    if config["kind"] == "scan":
        result = scan(before, translation_source=bool(config.get("translation_source")))
        expected = {str(key): int(value) for key, value in config.get("minimum_counts", {}).items()}
        failures = [f"{rule_id}: expected >= {minimum}, got {result['counts'].get(rule_id, 0)}" for rule_id, minimum in expected.items() if int(result["counts"].get(rule_id, 0)) < minimum]
        unexpected = [rule_id for rule_id in config.get("absent_rules", []) if result["counts"].get(rule_id, 0)]
        failures.extend(f"{rule_id}: expected no finding" for rule_id in unexpected)
    elif config["kind"] == "manifest":
        result = scan_manifest(fixture.parent / str(config["manifest"]), translation_source=bool(config.get("translation_source")))
        failures = []
        if len(result["documents_scanned"]) != int(config["expected_scanned"]):
            failures.append(f"expected {config['expected_scanned']} scanned documents")
        if len(result["documents_excluded"]) != int(config["expected_excluded"]):
            failures.append(f"expected {config['expected_excluded']} excluded documents")
        for rule_id, minimum in config.get("minimum_counts", {}).items():
            if int(result["counts"].get(rule_id, 0)) < int(minimum):
                failures.append(f"{rule_id}: expected >= {minimum}, got {result['counts'].get(rule_id, 0)}")
        for rule_id in config.get("absent_rules", []):
            if result["counts"].get(rule_id, 0):
                failures.append(f"{rule_id}: expected no finding")
    elif config["kind"] == "gate":
        result = gate(
            before,
            text_at(fixture, str(config["after"])),
            list(config.get("target_rules", [])),
            translation_source=bool(config.get("translation_source")),
            extra_values=None,
            preserved_rules=list(config.get("preserved_rules", [])),
        )
        failures = [] if result["status"] == config["expected_status"] else [f"expected {config['expected_status']}, got {result['status']}"]
    elif config["kind"] == "comparison":
        candidates = {str(name): text_at(fixture, str(path)) for name, path in config["candidates"].items()}
        result = compare(before, candidates, list(config.get("target_rules", [])), translation_source=bool(config.get("translation_source")), extra_values=None)
        expected = sorted(config["eligible_candidates"])
        actual = sorted(result["eligible_candidates"])
        failures = [] if actual == expected else [f"expected eligible {expected}, got {actual}"]
    elif config["kind"] == "coverage":
        scan_result = scan(before, translation_source=bool(config.get("translation_source")))
        rows = build_rows(scan_result)
        for row in rows:
            row["review_method"] = str(config.get("review_method", "unreviewed"))
            row["verdict"] = str(config.get("verdict", "unreviewed"))
        result = evaluate(scan_result, rows, str(config["mode"]))
        failures = [] if result["status"] == config["expected_status"] else [f"expected {config['expected_status']}, got {result['status']}"]
        for phrase in config.get("expected_forbidden_claims", []):
            if phrase not in result["forbidden_claims"]:
                failures.append(f"missing forbidden claim: {phrase}")
    elif config["kind"] == "term_migration":
        after = text_at(fixture, str(config["after"]))
        term_map = json.loads(text_at(fixture, str(config["term_map"])))
        result = audit_term_migration(before, after, term_map)
        failures = []
        if result["status"] != config["expected_status"]:
            failures.append(f"expected {config['expected_status']}, got {result['status']}")
        if int(result["residue_count"]) != int(config.get("expected_residue_count", 0)):
            failures.append(f"expected residue count {config.get('expected_residue_count', 0)}, got {result['residue_count']}")
        if int(result["echo_candidate_count"]) < int(config.get("minimum_echo_candidates", 0)):
            failures.append(f"expected at least {config.get('minimum_echo_candidates', 0)} echo candidates, got {result['echo_candidate_count']}")
    else:
        return {"fixture": fixture.name, "status": "failed", "failures": ["unknown fixture kind"]}
    return {"fixture": fixture.name, "status": "passed" if not failures else "failed", "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, action="append", help="fixture directory; repeatable")
    args = parser.parse_args()
    fixture_dirs = args.fixtures or list(DEFAULT_FIXTURE_DIRS)
    fixtures = [path for directory in fixture_dirs for path in sorted(directory.glob("*.json"))]
    if not fixtures:
        print("no fixtures found", file=sys.stderr)
        return 1
    outcomes = [run_fixture(path) for path in fixtures]
    failed = [item for item in outcomes if item["status"] != "passed"]
    print(json.dumps({"fixture_count": len(outcomes), "failed": len(failed), "outcomes": outcomes}, ensure_ascii=False, indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
