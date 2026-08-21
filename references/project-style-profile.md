# 프로젝트 문체 프로필

책·연재물·조직 문서의 확정된 표기와 목소리 결정을 K-humanizer의 보편 규칙과 분리해 기록한다. 프로필은 사용자가 승인했거나 충분한 프로젝트 내부 대조로 확인한 값만 담는다.

```json
{
  "scope": "book-or-series-id",
  "number_style": [
    {"context": "measurement", "rule": "project decision", "exceptions": ["quotation", "official name"]}
  ],
  "self_reference": {"preferred": "project decision", "exceptions": ["quotation"]},
  "emphasis": {"markdown_bold": "preserve|review|remove-on-request"},
  "transition": [{"form": "project form", "disposition": "preserve|ask", "reason": "user-approved function"}],
  "approved_by_user": true
}
```

## 경계

- 숫자 한글·아라비아 표기, 1인칭, 청유형, 볼드 사용량 같은 결정은 다른 저자에게 옮기지 않는다.
- 프로필은 문법이나 사실보다 우선하지 않는다. 공식 명칭·직접 인용·법령·서지 표기는 원자료를 따른다.
- 단일 표본에서 모델이 취향을 추정해 확정하지 않는다. 불확실하면 `ask`다.
- 프로필이 `remove-on-request`라고 해도 사용자가 실제 서식 제거를 요청하지 않으면 Markdown 구조를 바꾸지 않는다.
- 확정 용어는 term map, 장르상 규칙 예외는 allow profile, 프로젝트 문체 결정은 이 프로필에 둔다.

프로필의 원고·저자·경로는 프로젝트 내부에만 두고 공개 스킬에는 예시 값이나 실측 횟수를 넣지 않는다.
