# Step 3: semantic-search

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` — §3 `src/semantic_search.py` 책임, §4.4 의미 검색 흐름, §6 모델 오류, §7 캐시 전략
- `/docs/ADR.md` — ADR-006 EmbeddingGemma 300M, ADR-007 prepare_model.py, ADR-008 Top 3 무임계값
- `/docs/PRD.md` — FR-5 의미 검색, §7 성능과 자원
- `/src/rtzr_client.py` — Utterance 구조 확인
- `/src/segments.py` — AnswerSegment 구조 확인
- `/tests/conftest.py` — 공용 fixture

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

### 1. `src/semantic_search.py` 구현

EmbeddingGemma 300M을 이용한 로컬 의미 검색 모듈을 구현한다.

#### 함수 시그니처

```python
def load_model(device: str | None = None, local_files_only: bool = True) -> SentenceTransformer:
    """EmbeddingGemma 300M 모델을 로드한다.

    장치 선택:
    1. device가 명시되면 해당 장치를 사용한다.
    2. device가 None이면 MPS 사용 가능 여부를 확인한다.
    3. MPS 로드 또는 짧은 추론이 실패하면 CPU로 한 번만 대체한다.
    4. CPU에서도 실패하면 RuntimeError를 발생시킨다.

    반환된 모델의 실제 device를 확인할 수 있어야 한다.
    """

def embed_documents(model: SentenceTransformer, texts: list[str]) -> np.ndarray:
    """답변 텍스트를 임베딩한다.

    - prompt_name="Retrieval-document"
    - normalize_embeddings=True
    - batch_size=8
    - 반환: (N, D) ndarray
    """

def embed_query(model: SentenceTransformer, query: str) -> np.ndarray:
    """질의 텍스트를 임베딩한다.

    - prompt_name="Retrieval-query"
    - normalize_embeddings=True
    - 반환: (1, D) 또는 (D,) ndarray
    """

def search_top_k(
    query_embedding: np.ndarray,
    doc_embeddings: np.ndarray,
    k: int = 3,
) -> list[tuple[int, float]]:
    """코사인 유사도 기반 Top K를 반환한다.

    - 이미 정규화된 벡터이므로 dot product = cosine similarity
    - 내림차순 정렬
    - 반환: [(index, similarity), ...], 길이 = min(k, len(doc_embeddings))
    - doc_embeddings가 비어있으면 빈 리스트 반환
    """
```

#### 핵심 규칙

- 모델 이름은 `"google/embeddinggemma-300m"`으로 고정한다. 설정으로 변경할 수 없게 한다.
- `local_files_only=True`가 기본이다. 앱 실행 중 모델을 다운로드하지 않는다.
- MPS 폴백은 1회만 시도한다. MPS 실패 → CPU 시도 → CPU도 실패 → RuntimeError.
- 임베딩 프롬프트는 `Retrieval-query`와 `Retrieval-document`를 정확히 사용한다.
- 절대 점수 임계값, 높음/보통/낮음 구간을 정의하지 않는다.
- `search_top_k`는 순수 numpy 연산이다. 모델 의존성이 없어야 한다.
- `sentence_transformers` 라이브러리만 사용한다. 직접 transformers + torch로 인코딩하지 않는다.

### 2. `scripts/prepare_model.py` 구현

앱 실행 전에 모델을 다운로드하고 검증하는 스크립트다.

```python
"""EmbeddingGemma 300M 모델을 다운로드하고 검증한다.

사용법: python scripts/prepare_model.py
"""
```

수행 단계:

1. `.env`에서 `HF_TOKEN`을 로드한다 (`python-dotenv` 사용).
2. `HF_TOKEN`이 없으면 에러 메시지를 출력하고 종료한다.
3. `google/embeddinggemma-300m` 모델을 `SentenceTransformer`로 다운로드한다 (`local_files_only=False`).
4. 모델을 로드하고 사용된 장치(MPS/CPU)를 출력한다.
5. 짧은 질의와 문서 텍스트로 임베딩을 생성한다:
   - query: `"테스트 질의"`
   - document: `"테스트 문서"`
   - 각각 `Retrieval-query`, `Retrieval-document` 프롬프트 사용
6. 두 임베딩의 shape와 norm을 확인하고 결과를 출력한다.
7. 성공하면 `"모델 준비 완료"` 메시지를 출력한다.

#### 핵심 규칙

- 이 스크립트는 `local_files_only=False`로 다운로드한다 (앱과 다름).
- 모델 파일을 프로젝트 폴더에 복사하거나 Git에 포함하지 않는다.
- `HF_TOKEN` 값 자체를 출력하지 않는다.

### 3. `tests/test_semantic_search.py` 구현

단위 테스트를 작성한다. 실제 모델 로드 없이 테스트할 수 있도록 모킹한다.

테스트할 항목:

- **search_top_k 정렬**: 유사도 내림차순으로 반환되는지 확인 (numpy 벡터로 직접 테스트)
- **search_top_k 결과 수**: k=3이고 문서가 5개 → 3개 반환
- **search_top_k 문서 부족**: k=3이고 문서가 2개 → 2개 반환
- **search_top_k 문서 0개**: 빈 ndarray → 빈 리스트 반환
- **search_top_k 문서 1개**: k=3이고 문서가 1개 → 1개 반환
- **embed_documents 호출**: model.encode가 올바른 인자(prompt_name, normalize_embeddings, batch_size)로 호출되는지 mock 검증
- **embed_query 호출**: model.encode가 올바른 인자(prompt_name, normalize_embeddings)로 호출되는지 mock 검증
- **load_model MPS 폴백**: MPS 로드 실패 시 CPU로 재시도하는 로직 mock 테스트

## Acceptance Criteria

```bash
python -m pytest tests/test_semantic_search.py tests/test_segments.py tests/test_rtzr_client.py -v
```

- 모든 테스트가 통과한다.
- 실제 모델 다운로드나 GPU 접근 없이 실행된다.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `src/semantic_search.py`가 Streamlit에 의존하지 않는가?
   - 모델 이름이 `"google/embeddinggemma-300m"`으로 하드코딩되어 있는가?
   - 유사도 임계값이나 높음/보통/낮음 구간이 정의되어 있지 않은가?
   - `search_top_k`가 순수 numpy 연산인가?
   - `scripts/prepare_model.py`가 `HF_TOKEN` 값을 출력하지 않는가?
3. 결과에 따라 `phases/0-mvp/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 유사도 임계값(threshold)을 정의하지 마라. 이유: ADR-008에서 무임계값으로 결정했다.
- 높음/보통/낮음 구간을 정의하지 마라. 이유: 유사도는 정렬용 값이다.
- 앱 실행 중(`local_files_only=True`) 모델을 다운로드하지 마라. 이유: ADR-007에서 사전 준비로 결정했다.
- `transformers` 라이브러리로 직접 인코딩하지 마라. 이유: `sentence_transformers`의 프롬프트 기능을 사용한다.
- 모델 이름을 파라미터화하지 마라. 이유: MVP는 EmbeddingGemma 300M만 사용한다.
- `st.cache_resource`를 이 모듈에서 사용하지 마라. 이유: 캐싱은 app.py의 책임이다.
- 기존 테스트를 깨뜨리지 마라.
