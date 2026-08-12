# 다의어·선별 이관 계약 v0.1

같은 기존어를 모두 한 확정어로 바꾸지 않는다. 한 표기가 문맥에 따라 서로 다른 개념을 가리키면, 먼저 용례를 분류하고 각 위치의 결정을 잠근다. 이것은 번역어를 자동으로 정하는 기능이 아니다.

## 1. 언제 쓰는가

- 하나의 표기가 분량·출처·언어·가공 상태처럼 서로 다른 개념 축을 가리킬 때
- 전면 통일이 책의 장 제목·논증 구별·전문 용어를 무너뜨릴 때
- 같은 동사나 정의 자리에 여러 용어가 섞여 독자가 구별을 찾게 될 때

전역 단일 치환은 [terminology-migration.md](terminology-migration.md)를 쓴다. 이 계약은 `한 표기 → 여러 결정`일 때만 추가한다.

## 2. 용례 결정 대장

```json
{
  "schema_version": "0.1",
  "terms": [
    {
      "id": "source-text",
      "forms": ["기존 표기"],
      "senses": [
        {"id": "full-text", "definition": "축약 전의 글 전체"},
        {"id": "first-source", "definition": "재인용 전 최초 출처"}
      ],
      "occurrences": [
        {
          "document_id": "chapter-1",
          "scope": "body",
          "line": 12,
          "occurrence": 1,
          "after_line": 12,
          "after_occurrence": 1,
          "form": "기존 표기",
          "sense": "first-source",
          "decision": "replace",
          "after": "확정 표기",
          "rationale": "재인용의 출처를 가리킴"
        }
      ]
    }
  ]
}
```

- `senses`는 원고 안에서 구별할 개념 축과 정의다. 정답 목록이 아니다.
- `occurrences`에는 **기존어의 모든 비보호 용례**를 변경 전 `document_id·scope·line·occurrence`로 한 번씩 기록한다. `replace`와 `preserve`에는 변경 후의 `after_line·after_occurrence`도 기록한다. 같은 줄에서 앞 용례를 바꿨다면 뒤 용례의 순번이 달라질 수 있으므로, 변경 전 순번을 재사용하지 않는다.
- `decision`은 `replace`, `preserve`, `ask` 중 하나다. `replace`는 `after`를, `preserve`와 `ask`는 그 이유를 적는다.
- 인용·고유명·역사적 용례는 기존 term map의 정확 위치 예외를 쓴다. 대장을 비워 검사를 피하지 않는다.

## 3. 감사

```bash
python3 scripts/audit_selective_terms.py \
  --manifest migration-manifest.json --sense-map sense-map.json
```

감사기는 manifest의 단순 Markdown scope에서 다음만 확인한다.

1. 기존어의 모든 비보호 용례가 정확히 한 결정으로 덮였는지
2. 대장 좌표가 변경 전·후 파일 모두에 존재하는지
3. `replace` 위치에 지정한 `after` 표기가, `preserve` 위치에 기존 표기가 남았는지
4. `ask`가 남아 있으면 결과를 `보류`로 하는지

`기계 확인 완료`는 개념 분류의 옳음·연어·의미 보존·전수 문맥 독해의 통과가 아니다. 특히 줄 이동, 문장 합치기, 표·각주의 복잡한 Markdown은 보수적으로 `보류`하고 사람이 대장을 갱신한다.
