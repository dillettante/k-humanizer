#!/usr/bin/env python3
"""API 자격 증명을 저장하지 않고 KCI 논문 메타데이터를 수집한다.

KCI 제목과 초록은 로컬의 비공개 근거 폴더에만 둔다. 공개 스킬에는
검토한 집계값과 논문 단위 주장만 쓰며, 이 수집 결과는 넣지 않는다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_MANIFEST = SKILL_DIR / "references" / "kci-query-manifest.json"
DEFAULT_OUTPUT = SKILL_DIR / "evidence" / "private" / "kci"


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def child(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element if local_name(item) == name), None)


def text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    value = " ".join(element.text.split())
    return value or None


def values(group: ET.Element | None, item_name: str) -> list[dict[str, object]]:
    if group is None:
        return []
    return [
        {"value": text(item), "attributes": dict(item.attrib)}
        for item in group
        if local_name(item) == item_name and text(item)
    ]


def scalar(parent: ET.Element | None, name: str) -> str | None:
    return text(child(parent, name)) if parent is not None else None


def extract_records(root: ET.Element) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for record in (item for item in root.iter() if local_name(item) == "record"):
        journal = child(record, "journalInfo")
        article = child(record, "articleInfo")
        if article is None:
            continue
        title_group = child(article, "title-group")
        author_group = child(article, "author-group")
        abstract_group = child(article, "abstract-group")
        article_id = article.attrib.get("article-id")
        records.append(
            {
                "source": "KCI Open API",
                "source_id": f"KCI:{article_id}" if article_id else None,
                "article_id": article_id,
                "journal": {
                    "name": scalar(journal, "journal-name"),
                    "publisher": scalar(journal, "publisher-name"),
                    "year": scalar(journal, "pub-year"),
                    "month": scalar(journal, "pub-mon"),
                    "volume": scalar(journal, "volume"),
                    "issue": scalar(journal, "issue"),
                },
                "titles": values(title_group, "article-title"),
                "authors": values(author_group, "author"),
                "abstracts": values(abstract_group, "abstract"),
                "categories": values(child(article, "article-categories"), "category"),
                "pages": {"first": scalar(article, "fpage"), "last": scalar(article, "lpage")},
                "doi": scalar(article, "doi"),
                "uci": scalar(article, "uci"),
                "url": scalar(article, "url"),
                "citation_count": scalar(article, "citation-count"),
                "verified": scalar(article, "verified"),
            }
        )
    return records


def parse_response(payload: bytes) -> tuple[ET.Element, int | None]:
    root = ET.fromstring(payload)
    errors = [text(item) for item in root.iter() if local_name(item) in {"error", "message"}]
    if any(errors):
        raise RuntimeError("KCI returned an error response")
    total = next((text(item) for item in root.iter() if local_name(item) == "total"), None)
    return root, int(total) if total and total.isdigit() else None


def fetch(endpoint: str, params: dict[str, str], attempts: int, delays: list[int]) -> bytes:
    # The complete URL contains a credential.  It must never be logged or written.
    request = urllib.request.Request(f"{endpoint}?{urllib.parse.urlencode(params)}")
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(delays[min(attempt, len(delays) - 1)])
    raise AssertionError("unreachable")


def redact(payload: bytes, secret: str) -> bytes:
    cleaned = payload.replace(secret.encode("utf-8"), b"***REDACTED***")
    if secret.encode("utf-8") in cleaned:
        raise RuntimeError("credential redaction failed")
    return cleaned


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    manifest = json.loads(args.query_file.read_text(encoding="utf-8"))
    source = manifest["source"]
    request_config = manifest["request"]
    secret = os.environ.get(args.api_key_env or source["credential_env"])
    if not secret:
        raise RuntimeError(f"required environment variable is not set: {args.api_key_env or source['credential_env']}")

    selected = set(args.groups.split(",")) if args.groups else None
    groups = [group for group in manifest["query_groups"] if not selected or group["id"] in selected]
    if not groups:
        raise RuntimeError("no query groups selected")

    if args.dry_run:
        print(json.dumps({"groups": [group["id"] for group in groups], "requests": sum(len(group["terms"]) * len(request_config["fields"]) for group in groups), "credential": "environment-variable-present"}, ensure_ascii=False))
        return 0

    if args.resume:
        output = args.resume.resolve()
        raw_dir = output / "raw"
        if not output.is_dir() or not raw_dir.is_dir():
            raise RuntimeError("--resume must name an existing collection run with a raw directory")
        run_id = output.name
    else:
        run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = args.output_root / run_id
        raw_dir = output / "raw"
        output.mkdir(parents=True, exist_ok=False)
        raw_dir.mkdir()

    retries = request_config["retry"]
    records_path = output / "records.jsonl"
    collected = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines() if line] if records_path.exists() else []
    seen_article_ids = {str(record.get("article_id") or record.get("source_id")) for record in collected if record.get("article_id") or record.get("source_id")}
    query_log_path = output / "query-log.json"
    query_log: list[dict[str, object]] = json.loads(query_log_path.read_text(encoding="utf-8")) if query_log_path.exists() else []
    completed_pages = {
        (str(item.get("group")), str(item.get("field")), str(item.get("term")), int(item.get("page", 0)))
        for item in query_log
        if item.get("status") in {"ok", "repeated-page-stopped"}
    }
    failures: list[dict[str, str]] = []
    last_request_at: float | None = None

    for group_index, group in enumerate(groups, start=1):
        for term_index, term in enumerate(group["terms"], start=1):
            for field in request_config["fields"]:
                fingerprints: set[str] = set()
                for page in range(1, args.max_pages + 1):
                    query_key = (group["id"], field, term, page)
                    if query_key in completed_pages:
                        continue
                    params = {
                        "key": secret,
                        "apiCode": source["api_code"],
                        field: term,
                        "page": str(page),
                        "displayCount": str(request_config["display_count_max"]),
                    }
                    try:
                        if last_request_at is not None and args.rate_limit_seconds:
                            time.sleep(max(0, args.rate_limit_seconds - (time.monotonic() - last_request_at)))
                        payload = fetch(source["endpoint"], params, retries["max_attempts"], retries["backoff_seconds"])
                        last_request_at = time.monotonic()
                        root, total = parse_response(payload)
                        records = extract_records(root)
                    except Exception as error:  # Preserve a non-secret diagnostic only.
                        failures.append({"group": group["id"], "field": field, "term": term, "page": str(page), "error": type(error).__name__})
                        break

                    fingerprint = hashlib.sha256("|".join(record.get("article_id") or "" for record in records).encode("utf-8")).hexdigest()
                    if fingerprint in fingerprints:
                        query_log.append({"group": group["id"], "field": field, "term": term, "page": page, "total": total, "records": len(records), "status": "repeated-page-stopped"})
                        break
                    fingerprints.add(fingerprint)

                    safe_payload = redact(payload, secret)
                    raw_path = raw_dir / f"g{group_index:02d}-t{term_index:02d}-{field}-p{page:03d}.xml"
                    if raw_path.exists():
                        raise RuntimeError("refusing to overwrite an existing raw response")
                    raw_path.write_bytes(safe_payload)
                    new_records = 0
                    for record in records:
                        article_id = record.get("article_id")
                        dedupe_key = str(article_id) if article_id else hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
                        if dedupe_key not in seen_article_ids:
                            seen_article_ids.add(dedupe_key)
                            collected.append(record)
                            new_records += 1
                    query_log.append({"group": group["id"], "field": field, "term": term, "page": page, "total": total, "records": len(records), "new_records": new_records, "status": "ok"})
                    if not records:
                        break

    with records_path.open("w", encoding="utf-8") as stream:
        for record in collected:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_json(query_log_path, query_log)
    write_json(output / "run.json", {"run_id": run_id, "source": source["name"], "records_unique": len(collected), "queries_completed": len(query_log), "failures": failures, "credential": "not persisted"})
    print(json.dumps({"run_id": run_id, "records_unique": len(collected), "queries_completed": len(query_log), "failures": len(failures), "output": str(output)}, ensure_ascii=False))
    return 0 if not failures else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-file", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--groups", help="쉼표로 구분한 질의 그룹 ID")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--resume", type=Path, help="완료한 쪽을 다시 요청하지 않고 이전 수집을 이어갈 경로")
    parser.add_argument("--rate-limit-seconds", type=float, default=0.0, help="성공한 API 요청 사이의 최소 대기 시간(초)")
    parser.add_argument("--api-key-env", help="매니페스트의 자격 증명 환경 변수 이름을 덮어씀")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.max_pages < 1:
        parser.error("--max-pages는 1 이상이어야 합니다")
    if args.rate_limit_seconds < 0:
        parser.error("--rate-limit-seconds는 0 이상이어야 합니다")
    try:
        return run(args)
    except Exception as error:
        print(f"수집 실패: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
