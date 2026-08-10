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

## 필요한 상태값

- `hold`: 그럴듯한 후보이지만 윤문 권고나 횟수 주장을 하지 않는다.
- `provisional`: 출처, 결정 가능한 기준 또는 위치가 확인된 예문, 반례가 있는 후보다.
- `confirmed`: 독립적인 한국어 평가, 뜻 보존 검토, 적용 유형별 정밀도 검사를 통과했다.
- `retired`: 감사를 위해 남기되 더는 권고하지 않는다.

## 반드시 지킬 단서

1. 문체 진단과 저자 판별을 분리한다.
2. 번역 자연스러움과 번역 충실성을 분리한다.
3. 근거 없는 모델 추정치를 횟수로 바꾸지 않는다.
4. 짧은 글 기준에서 걸렸다는 이유만으로 긴 글, 의도한 호흡, 계획된 상호참조를 오류로 단정하지 않는다.
5. 비공개 원고, 스캔, API 응답, 개인 규칙, 절대 경로를 공개 스킬에 넣지 않는다.
