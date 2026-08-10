#!/usr/bin/env python3
"""Run public deterministic scan and gate fixtures without network access."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scan_style import scan
from verify_style_gate import gate


DEFAULT_FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures-public"


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
    elif config["kind"] == "gate":
        result = gate(before, text_at(fixture, str(config["after"])), list(config.get("target_rules", [])), translation_source=bool(config.get("translation_source")), extra_values=None)
        failures = [] if result["status"] == config["expected_status"] else [f"expected {config['expected_status']}, got {result['status']}"]
    else:
        return {"fixture": fixture.name, "status": "failed", "failures": ["unknown fixture kind"]}
    return {"fixture": fixture.name, "status": "passed" if not failures else "failed", "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    args = parser.parse_args()
    fixtures = sorted(args.fixtures.glob("*.json"))
    if not fixtures:
        print("no fixtures found", file=sys.stderr)
        return 1
    outcomes = [run_fixture(path) for path in fixtures]
    failed = [item for item in outcomes if item["status"] != "passed"]
    print(json.dumps({"fixture_count": len(outcomes), "failed": len(failed), "outcomes": outcomes}, ensure_ascii=False, indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
