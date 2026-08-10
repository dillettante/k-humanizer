#!/usr/bin/env python3
"""공개 KCI 논문 PDF를 로컬 비공개 근거 저장소로 가져온다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "evidence" / "private" / "papers" / "kci"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--journal-slug", help="KCI 학술지 호스트 구간. 예: kats")
    location.add_argument("--orte-file-id", help="KCI 포털 전문 식별자. 예: KCI_FI002785155")
    parser.add_argument("--article-id", required=True, help="KCI 논문 식별자. 예: ART001059071")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.journal_slug and not re.fullmatch(r"[a-z0-9-]+", args.journal_slug):
        parser.error("--journal-slug에는 소문자, 숫자, 하이픈만 쓸 수 있습니다")
    if args.orte_file_id and not re.fullmatch(r"KCI_FI\d+", args.orte_file_id):
        parser.error("--orte-file-id는 KCI_FI 뒤에 숫자가 오는 형식이어야 합니다")
    if not re.fullmatch(r"ART\d+", args.article_id):
        parser.error("--article-id는 ART 뒤에 숫자가 오는 형식이어야 합니다")

    if args.journal_slug:
        source_label = "KCI journal archive"
        source_folder = args.journal_slug
        article_page = f"https://journal.kci.go.kr/{args.journal_slug}/archive/articleView?artiId={args.article_id}"
        pdf_url = f"https://journal.kci.go.kr/{args.journal_slug}/archive/articlePdf?artiId={args.article_id}"
    else:
        source_label = "KCI portal"
        source_folder = "portal"
        article_page = f"https://www.kci.go.kr/kciportal/landing/article.kci?arti_id={args.article_id}"
        pdf_url = "https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiOrteServHistIFrame.kci?" + urllib.parse.urlencode({"sereArticleSearchBean.artiId": args.article_id, "sereArticleSearchBean.orteFileId": args.orte_file_id})
    request = urllib.request.Request(pdf_url, headers={"User-Agent": "Mozilla/5.0", "Referer": article_page})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    if not payload.startswith(b"%PDF-"):
        raise RuntimeError("KCI 응답이 PDF가 아닙니다")

    output = args.output_root / source_folder
    output.mkdir(parents=True, exist_ok=True)
    pdf_path = output / f"{args.article_id}.pdf"
    metadata_path = output / f"{args.article_id}.json"
    if pdf_path.exists() or metadata_path.exists():
        raise RuntimeError("기존 근거 파일을 덮어쓰지 않습니다")
    pdf_path.write_bytes(payload)
    metadata_path.write_text(
        json.dumps(
            {
                "source": source_label,
                "article_id": args.article_id,
                "article_page": article_page,
                "pdf_url": pdf_url,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "public_distribution": "not included in the public K-humanizer repository",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"article_id": args.article_id, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "output": str(pdf_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
