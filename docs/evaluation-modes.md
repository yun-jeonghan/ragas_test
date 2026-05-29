# 평가 항목과 모드

이 프로젝트는 질문 유형과 평가 항목을 분리해서 봅니다.

## 질문 모드

### local

- 특정 인물, 엔티티, 문서, 관계를 직접 찾는 질문
- 예: "Scrooge는 누구야?"
- 보통 GraphRAG local search를 쓴다

### global

- 여러 커뮤니티를 묶어서 전체 요약이 필요한 질문
- 예: "이 문서 집합의 큰 주제는 뭐야?"
- 보통 GraphRAG global search를 쓴다

### multi-hop

- 두세 단계 이상 관계를 따라가야 하는 질문
- 예: "A와 B의 관계를 통해 C를 설명해줘"

### comparison

- 두 대상이나 두 집단을 비교하는 질문
- 예: "A와 B는 어떻게 달라?"

### unanswerable

- 근거가 충분하지 않은 질문
- 모델이 모른다고 말할 수 있는지 확인한다

## Ragas 평가 항목

### context_precision

- 가져온 컨텍스트 중 실제로 유용한 비율
- 노이즈가 많은 검색을 잡아내기 좋다

### context_recall

- 정답에 필요한 근거를 얼마나 빠뜨리지 않았는지
- 검색 누락을 잡는 데 중요하다

### faithfulness

- 답변이 검색 컨텍스트에 얼마나 충실한지
- 환각 여부를 보는 핵심 지표다

### answer_relevancy

- 답변이 질문 의도에 얼마나 맞는지
- 질문과 무관한 장황한 답을 잡아낸다

## GraphRAG 전용 추가 항목

### graph_path_accuracy

- 정답에 도달하는 엔티티/관계 경로가 맞는지

### community_coverage

- 필요한 커뮤니티 요약을 제대로 썼는지

### entity_coverage

- 핵심 엔티티를 빠뜨리지 않았는지

### citation_consistency

- 인용한 근거와 답변 내용이 일치하는지

### mode_match

- 질문 타입에 맞는 local/global 모드를 골랐는지

## 질문 자동 생성

가능하다.

추천 방식은 두 가지다.

1. 원문 문서 또는 GraphRAG text unit에서 질문을 생성한다
2. community report, entity, relationship을 바탕으로 질문을 생성한다

실무적으로는 아래 순서가 좋다.

- local 질문은 text unit과 entity에서 생성
- global 질문은 community report에서 생성
- multi-hop 질문은 relationship 경로를 따라 생성
- unanswerable 질문은 근거가 부족한 문서 조합에서 생성

중요한 점은 자동 생성 질문도 사람이 한 번은 샘플링해서 검수해야 한다는 것이다.
자동 생성만 믿으면 질문이 너무 쉬워지거나, 정답 라벨이 애매해질 수 있다.

