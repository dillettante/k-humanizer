# 근거 상태

이 문서는 제안한 문형을 K-humanizer의 실제 규칙으로 올릴 수 있는지 판단할 때 쓴다. 인용 횟수, 탐지 정확도, 번역 연구의 관찰 하나만으로 안전한 윤문이라고 결론 내리지 않는다.

## 서지 확인을 마친 출발점

P2의 `KCI metadata + abstract` 확인은 서지와 후보 주장만 뜻한다. `full text`로 표시한 항목만 전문·예문·적용 범위를 대조했다. 아래 어떤 항목도 실제 규칙이나 `confirmed` 근거는 아니다.

| ID | 출처 | P2 상태 | 가능한 활용 | 한계 |
|---|---|---|---|---|
| KO-TRANS-2007 | [김정우 2007](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001059071) | provisional / 전문 | 번역투 유형과 처방 후보 | 문형별 판별 통계처럼 제시하지 않는다. |
| KO-TRANS-2009 | [김도훈 2009](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001410360) | provisional / 전문 | 영한 번역문의 대명사·복수 표지·무생물 주어 | 번역 맥락의 근거일 뿐, 한국어 창작 산문의 근거가 아니다. |
| KO-TRANS-2016 | [최희경 2016](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002094440) | provisional / 전문 | 표면 문형 하나만으로 번역투를 단정하지 않는 반례 | 전치사 관련 두 문형과 신문·잡지 말뭉치에 한정된다. |
| KO-PE-2018 | [윤미선 외 2018](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002414136) | provisional / 전문 | 영한 포스트에디팅 지침과 예문 | 점검표를 보편 임계값으로 바꾸지 않는다. |
| KO-PE-2021 | [김자경 2021](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002785155) | provisional / 전문 | 한영 포스트에디팅 결과의 정확성 위험 | 오류 사례 표본이므로 모집단 오류율을 추정하지 않는다. |
| KO-PE-2023 | [정재혁 2023](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002989426) | provisional / 전문 | 영한 포스트에디팅 정확성 비교 | 특정 기술 텍스트와 훈련 참가자에 한정되므로 보편 임계값이 아니다. |
| KO-PE-2024 | [정재혁 2024](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003053484) | provisional / 전문 | 영한 포스트에디팅 오류의 글 종류별 차이 | 텍스트와 표본이 제한되어 효과 크기를 일반화하지 않는다. |
| KO-FEEDBACK-2025 | [최숙기 2025](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003172871) | hold / 전문 | AI 글쓰기 피드백 품질의 후보 준거 | 연구 자체가 실제 적용과 추가 검증을 요청한다. |
| KO-LLM-2025 | [KatFishNet](https://aclanthology.org/2025.acl-long.1030/) | hold / P2에서 외부 출처 재감사하지 않음 | 한국어 LLM 텍스트 진단 특징과 벤치마크 | 탐지 특징은 자동 윤문 지시가 아니다. |
| KO-LLM-2026 | [Jeon 외 2026](https://aclanthology.org/2026.findings-eacl.77/) | hold / P2에서 외부 출처 재감사하지 않음 | 여러 장르·모델군에서의 한국어 비지도 LLM 텍스트 탐지 | K-humanizer는 저자 판별이나 탐지 회피를 하지 않는다. |
| XLT-LLM-2025 | [Lost in Literalism](https://aclanthology.org/2025.acl-long.630/) | hold / P2에서 외부 출처 재감사하지 않음 | 미세조정 자료와 번역투 자연스러움 가설 | 중영·독영 연구이므로 한국어 근거 없이는 옮겨 쓰지 않는다. |
| XLT-DISC-2025 | [한영 담화 시험 세트](https://aclanthology.org/2025.coling-main.110/) | hold / P2에서 외부 출처 재감사하지 않음 | 문맥·영형 대용·관용표현·함의 평가 설계 | 한영 방향의 연구이므로 영한 문체 규칙이 아니다. |

## v0.8 실행 후보의 경계

[`ai-style-taxonomy.md`](ai-style-taxonomy.md)의 표지는 저자 판별표나 자동 치환표가 아니다. 업스트림의 경험적 문형 목록, KCI 번역·포스트에디팅 연구의 적용 범위, 그리고 한국어 원고 검토에서 확인한 보존 원칙을 함께 대조해 만든 **문맥 의존적 작업 후보**다.

- 40개 분류 항목 중 26개만 결정적 위치 앵커를 가진다. 나머지는 문단·리듬·서식·용어 이관 맥락을 사람이 판정하는 항목이다.
- 각 표지는 위치, 기능, 보존 반례를 함께 확인할 때만 제안한다.
- 번역투 표지는 원문이 있거나 번역문이라는 맥락이 확인될 때에만 쓴다.
- 빈도·편집 비율·탐지율을 품질 임계값으로 제시하지 않는다.
- 효용과 과교정 위험은 [`evaluation-contract.md`](evaluation-contract.md)의 대조 사례로 검증한 뒤에만 강화한다.
- KH-S33은 한 실사용 보고에서 확인한 전역 용어 치환 후유증을 범용 절차로 일반화한 `provisional` 워크플로 항목이다. AI 작성 표지나 보편 번역어 판정이 아니며, 독립 corpus의 정밀도 검증 전에는 자동 수정 규칙으로 올리지 않는다.
- KH-S34~S37은 사람이 한 차례 편집한 장문에서 남을 수 있는 메타 발화·장면 회귀·예고·굵은 라벨 연쇄의 **위치 후보**다. 비공개 원고의 문장·용어·횟수는 공개하지 않았고, 공개 자작 fixture와 위치·다파일 분포 계약만으로 회귀를 검증한다. 단일 문서 또는 단일 앵커의 발견은 결함 판정이 아니다.
- 다의어·선별 이관 감사는 한 기존어를 전면 치환했을 때의 의미 축 붕괴를 막는 절차 후보다. 좌표·결정 완결성만 기계 확인하며, 개념 분류와 최종 용어는 사람이 판정한다.
- [신형철 교수 대담](https://www.youtube.com/watch?v=qE_wJVYPKh4)의 매끈함과 미끄러움, 강점과 거침, 뒤늦게 형성되는 감정에 관한 논의는 `강점 대장`과 `축약 불가 연쇄`의 개념적 출발점으로만 쓴다. 이는 AI 저자 판별, 보편적인 3항 금지, `야생성` 정량 점수의 경험적 근거가 아니다.
- KH-S40은 같은 대담에서 전언된 이른바 `3회 법칙`을 의미 중복 삼항 연쇄라는 중립적 편집 후보로 다시 정의한 `provisional` 규칙이다. scanner는 `-고/-며`로 연결된 세 항의 위치만 모집한다. 세 항이 동의어인지, 글의 결함인지, AI가 썼는지는 사람이 문맥과 원고 전체의 반복을 읽어 판정한다.

## v0.8 검증 상태

- 결정적 스캔·보호·gate·범위·반복 윤문·용어 이관·후편집 구조 후보 회귀 시험은 자작 공개 fixture와 단위 시험으로 검증한다.
- 목표 표지가 줄지 않은 무수정본, 다른 표지를 새로 만든 후보, 실제 앵커가 없는 규칙을 보존 예외로 우회하는 후보는 모두 보류한다.
- DOCX 형식 스모크 시험은 이모지·굵은 본문·가짜 제목·목록 연속을 실제 OOXML 구조에서 찾는다.
- Markdown 구조 스모크 시험은 제목·굵은 표지·이모지·코드 펜스 유실을 보류한다.
- 자작 `raw_ai` 합성문과 비공개 `human_polished` 실제 원고로 전방 비교를 수행했다. 모델 평가는 버전과 도구명을 가린 `model-assisted blind review`로 기록하며, 사람 평가로 제시하지 않는다.
- 맹검 도중 적극적 재구성이 원문의 제한된 명제를 강화하거나 새 과정을 만들 수 있다는 결함을 찾았다. 문단별 `의미 명세`와 재구성 후 명제 대조를 추가했다.
- 최종 합성문 1건의 model-assisted blind review에서 v0.3 후보는 기존 후보보다 AI식 공식성과 호흡 평가는 높았지만, `상호작용→반응`, `중요하다→도움이 된다`, `~한다→~할 수 있다`의 의미 약화가 발견됐다. 해당 후보는 문체 우세로만 기록하고 무조건 통과로 승격하지 않았다. 세 약화 유형을 의미 gate의 명시적 실패 예로 추가했다.
- 후편집 구조 후보는 `ai_edited`로 명시한 입력에서만 스캔하고, 문단 위치·제목 경로·문서별 분포·같은 shape의 다파일 반복을 결과에 남긴다. 이 결과는 사람의 전체 독해나 자동 삭제를 뜻하지 않는다.
- 강점 보존과 축약 불가 연쇄는 공개 대조 fixture로 구조 손실을 시험하되, 표현의 기능과 문학적 성취는 사람의 판정을 요구하는 `provisional` 계약이다.
- KH-S40의 위치 수집은 의미 중복 예문과 서로 다른 실제 절차 예문을 모두 후보로 반환하는 공개 fixture로 검증한다. 이는 높은 정밀도의 의미 판별기가 아니라 사람 검토를 위해 재현율을 우선한 위치 모집기다.
- 일반 독자를 대상으로 한 독립적인 맹검 사람 평가는 아직 필요하다. 그전까지 생성 품질 규칙을 `confirmed`로 올리지 않는다.

## 필요한 상태값

- `hold`: 그럴듯한 후보이지만 윤문 권고나 횟수 주장을 하지 않는다.
- `provisional`: 출처, 결정 가능한 기준 또는 위치가 확인된 예문, 반례가 있는 후보다.
- `confirmed`: 독립적인 한국어 평가, 뜻 보존 검토, 적용 유형별 정밀도 검사를 통과했다.
- `retired`: 감사를 위해 남기되 더는 권고하지 않는다.

## 반드시 지킬 단서

1. 문체 진단과 저자 판별을 분리한다.
2. 번역 자연스러움과 번역 충실성을 분리한다.
3. 근거 없는 모델 추정치를 횟수로 바꾸지 않는다.
4. 짧은 글 기준에서 걸렸다는 이유만으로 긴 글, 의도한 호흡, 계획된 상호참조를 오류로 단정하지 않는다. 특히 후편집 구조 후보는 다파일 분포와 서사 기능을 읽기 전에는 수정하지 않는다.
5. 비공개 원고, 스캔, API 응답, 개인 규칙, 절대 경로를 공개 스킬에 넣지 않는다.
