# 장르 allowlist

`--protect-file`은 특정 문자열을 손대지 않게 보호한다. 반면 allowlist는 **특정 규칙이 특정 위치에서 장르상 결함이 아님**을 선언한다. allowlist는 해당 finding을 지우지 않고 `allowed_counts`와 이유로 분리한다. 따라서 다른 규칙의 문제나 예외 남용을 가리지 않는다.

## JSON 형식

```json
{
  "genre": "legal-reference",
  "allow": [
    {
      "rule_id": "KH-S16",
      "scope": "all",
      "reason": "정식 기관명과 약어의 첫 병기다."
    },
    {
      "rule_id": "KH-S01",
      "scope": "heading",
      "reason": "제목의 대조가 이 장르의 논증 형식이다."
    }
  ]
}
```

- `genre`: 비어 있지 않은 장르 설명이다.
- `rule_id`: `quick-rules.json`에 있는 KH-S ID다.
- `scope`: `all`, `heading`, `body`, `first_sentence` 중 하나다. `first_sentence`는 본문 문단의 첫 문장만 뜻한다.
- `reason`: taxonomy의 보존 조건이나 문서 기능을 적는다. 단순히 “많아서”는 이유가 아니다.

같은 `rule_id`와 `scope` 조합은 한 번만 선언한다. 예외는 가장 좁은 범위부터 잡고, 원고 전체의 다른 후보는 계속 읽는다.

## 실행과 결과

```bash
python3 scripts/scan_style.py \
  --input draft.md \
  --allow-profile genre-allow.json \
  --output scan.json

python3 scripts/verify_style_gate.py \
  --before draft.md --after edited.md \
  --allow-profile genre-allow.json \
  --target-rule KH-S02
```

결과에서 다음을 구분한다.

- `counts`: 여전히 사람이 판정할 일반 후보
- `allowed_counts`: allowlist의 장르 예외 후보
- `all_counts`: 둘을 합친 실제 검출 수
- `findings[].allowed`, `allow_scope`, `allow_reason`: 개별 예외의 위치와 근거

allowlist는 문체 변경을 승인하거나 의미 보존을 보장하지 않는다. 직접 인용·법령·판결문 본문처럼 실제 문장을 고치면 안 되는 구간은 여전히 보호 블록이나 `--protect-file`로 따로 처리한다.
