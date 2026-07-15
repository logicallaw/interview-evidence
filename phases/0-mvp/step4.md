# Step 4: exporters

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` — §3 `src/exporters.py` 책임, §9 보안과 데이터 수명
- `/docs/ADR.md` — ADR-010 메모리 기반 JSON 다운로드
- `/docs/PRD.md` — FR-7 JSON 다운로드 (허용 필드 목록)
- `/src/rtzr_client.py` — Utterance 구조 확인
- `/src/segments.py` — AnswerSegment 구조 확인
- `/src/semantic_search.py` — search_top_k 반환 형태 확인

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

### 1. `src/exporters.py` 구현

현재 검색 결과를 JSON으로 내보내는 모듈을 구현한다.

#### 함수 시그니처

```python
def build_export_payload(
    audio_filename: str,
    query: str,
    candidate_speaker: str,
    results: list,
) -> dict:
    """현재 질의와 검색 결과로 export payload를 구성한다.

    results의 각 항목은 다음 정보를 포함한다:
    - rank: int (1-based)
    - similarity: float
    - text: str
    - start_at_ms: int
    - end_at_ms: int
    - source_utterance_indexes: list[int]

    반환 dict 구조:
    {
        "audio_filename": str,
        "query": str,
        "created_at": str (ISO 8601),
        "candidate_speaker": str,
        "results": [
            {
                "rank": int,
                "similarity": float,
                "text": str,
                "start_at_ms": int,
                "end_at_ms": int,
                "source_utterance_indexes": list[int]
            }
        ]
    }

    허용 필드 외의 데이터(음원, 전체 전사문, RTZR 원본 응답, 인증 정보)는
    인자로 받지도 않고 payload에 포함하지도 않는다.
    """

def serialize_export(payload: dict) -> bytes:
    """payload를 UTF-8 JSON 바이트로 직렬화한다.

    - ensure_ascii=False (한글 유지)
    - indent=2 (읽기 편의)
    - 반환: bytes
    """
```

#### 핵심 규칙

- `created_at`은 `datetime.now().isoformat()`로 생성한다. 타임존은 로컬 시간을 사용한다.
- 허용되지 않은 필드가 results 항목에 있으면 무시한다 (명시적 allowlist 방식).
- `similarity`는 float 그대로 유지한다 (반올림하지 않는다).
- `source_utterance_indexes`는 정수 리스트 그대로 유지한다.
- 범용 export 프레임워크를 만들지 않는다. 정확히 현재 질의와 Top 3만 처리한다.

### 2. `tests/test_exporters.py` 구현

단위 테스트를 작성한다.

테스트할 항목:

- **허용 필드만 포함**: payload에 정의된 6개 최상위 필드만 존재하는지 확인
- **results 필드**: 각 result에 6개 필드(rank, similarity, text, start_at_ms, end_at_ms, source_utterance_indexes)만 존재
- **created_at 형식**: ISO 8601 파싱 가능
- **한글 인코딩**: serialize_export 결과를 UTF-8 디코드 후 한글 텍스트가 유지되는지 확인
- **빈 결과**: results가 빈 리스트일 때 정상 동작
- **similarity 정밀도**: float 값이 반올림 없이 유지되는지 확인
- **직렬화 바이트**: serialize_export가 bytes 타입을 반환하는지 확인
- **역직렬화**: serialize_export 결과를 json.loads로 파싱 가능한지 확인

## Acceptance Criteria

```bash
python -m pytest tests/test_exporters.py tests/test_segments.py tests/test_rtzr_client.py tests/test_semantic_search.py -v
```

- 모든 테스트(exporters + 기존 모듈 전부)가 통과한다.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `src/exporters.py`가 Streamlit, requests, torch에 의존하지 않는가?
   - 허용 필드 외의 데이터를 인자로 받지 않는가?
   - `ensure_ascii=False`로 한글을 유지하는가?
   - 범용 export 프레임워크가 아닌 단일 목적 함수인가?
3. 결과에 따라 `phases/0-mvp/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 전사 전체, 원본 API 응답, 인증 정보를 인자로 받지 마라. 이유: 개인정보 누출 표면을 넓힌다.
- `ensure_ascii=True`를 사용하지 마라. 이유: 한글이 이스케이프되어 읽기 어려워진다.
- similarity를 반올림하지 마라. 이유: 원본 정밀도를 유지해야 한다.
- 범용 export 클래스나 플러그인 시스템을 만들지 마라. 이유: 단일 용도 함수로 충분하다.
- Streamlit, requests, torch를 import하지 마라. 이유: 순수 직렬화 로직이다.
- 기존 테스트를 깨뜨리지 마라.
