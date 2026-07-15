# Step 6: integration

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 전체 구조와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` — §2 목표 디렉터리 구조, §8 테스트 전략
- `/docs/PRD.md` — §8 MVP 완료 조건
- `/docs/ADR.md` — 전체 ADR 확인
- `/docs/UI_GUIDE.md` — 문구와 색상 확인
- `/CLAUDE.md` — CRITICAL 규칙 전체
- `/src/rtzr_client.py` — Step 1 산출물
- `/src/segments.py` — Step 2 산출물
- `/src/semantic_search.py` — Step 3 산출물
- `/src/exporters.py` — Step 4 산출물
- `/app.py` — Step 5 산출물
- `/tests/test_rtzr_client.py` — Step 1 테스트
- `/tests/test_segments.py` — Step 2 테스트
- `/tests/test_semantic_search.py` — Step 3 테스트
- `/tests/test_exporters.py` — Step 4 테스트
- `/tests/fixtures/rtzr_completed.json` — Step 1 fixture
- `/tests/conftest.py` — 공용 설정
- `/requirements.txt` — 의존성
- `/README.md` — 현재 README

이전 step에서 만들어진 모든 코드를 꼼꼼히 읽고, 전체적인 일관성을 확인하라.

## 작업

### 1. Fixture 검증 강화

`tests/fixtures/rtzr_completed.json`이 실제 파서와 동일한 경로를 통과하는지 확인한다.

- `rtzr_client._validate_completed_response()`에 fixture JSON을 입력하여 `Utterance` 리스트가 정상 생성되는지 확인하는 테스트가 있는지 점검한다.
- 생성된 `Utterance` 리스트를 `segments.build_answer_segments()`에 넣어 `AnswerSegment` 리스트가 정상 생성되는지 확인하는 통합 테스트를 추가한다.
- fixture의 발화 데이터로 구성된 세그먼트 수, searchable 여부, 시간 경계가 합리적인지 검증한다.

이 테스트는 `tests/test_integration.py`에 작성한다.

### 2. 전체 테스트 실행

```bash
python -m pytest -v
```

모든 테스트 파일이 통과하는지 확인한다. 실패하는 테스트가 있으면 원인을 분석하고 수정한다.

### 3. 모듈 import 검증

```bash
python -c "from src.rtzr_client import authenticate, create_transcription, get_transcription, Utterance, TranscriptionJob; from src.segments import get_unique_speakers, validate_speaker_count, pick_representative_utterances, build_answer_segments, compute_playback_bounds, AnswerSegment; from src.semantic_search import load_model, embed_documents, embed_query, search_top_k; from src.exporters import build_export_payload, serialize_export; print('All imports OK')"
```

모든 공개 인터페이스가 import 가능한지 확인한다.

### 4. ARCHITECTURE.md 디렉터리 구조 일치 확인

ARCHITECTURE.md §2의 목표 구조와 실제 파일을 비교한다:

```
app.py                         ✓
scripts/prepare_model.py       ✓
src/__init__.py                ✓
src/rtzr_client.py             ✓
src/segments.py                ✓
src/semantic_search.py         ✓
src/exporters.py               ✓
tests/fixtures/rtzr_completed.json  ✓
tests/test_rtzr_client.py      ✓
tests/test_segments.py         ✓
tests/test_semantic_search.py  ✓
tests/test_exporters.py        ✓
requirements.txt               ✓
```

누락된 파일이 있으면 보고한다 (이 step에서 생성하지 않고 보고만 한다).

### 5. CRITICAL 규칙 위반 점검

모든 소스 파일을 읽고 다음을 확인한다:

- [ ] `app.py`에 금지 문구(`AI 분석`, `인사이트 생성`, `최적의 답변`, `높은 관련성`, `지원자 적합도`, `AI 점수`)가 없는가?
- [ ] `src/` 모듈이 Streamlit에 의존하지 않는가? (`import streamlit` 검색)
- [ ] 오류 메시지에 자격 증명이나 토큰이 노출되지 않는가?
- [ ] fixture에 식별 메타데이터가 없는가?
- [ ] 유사도 임계값이 코드에 정의되어 있지 않는가?
- [ ] 맞장구 병합 휴리스틱이 없는가?
- [ ] 모델 이름이 하드코딩(`google/embeddinggemma-300m`)되어 있는가?

위반 사항이 있으면 수정한다.

### 6. README 업데이트

`/README.md`를 업데이트하여 다음 내용을 포함한다:

- 프로젝트 설명 (한 줄)
- 설치 순서:
  1. `python -m venv .venv && source .venv/bin/activate`
  2. `pip install -r requirements.txt`
  3. `.env` 설정 (`.env.example` 참고)
  4. `python scripts/prepare_model.py`
  5. `python -m pytest` (단위 테스트)
  6. `streamlit run app.py`
- 기존 README 내용 중 유지할 부분은 보존한다.
- 실행 명령과 환경 변수 이름만 포함하고, 실제 자격 증명 값은 넣지 않는다.

## Acceptance Criteria

```bash
python -m pytest -v
python -c "from src.rtzr_client import authenticate, create_transcription, get_transcription, Utterance, TranscriptionJob; from src.segments import get_unique_speakers, validate_speaker_count, pick_representative_utterances, build_answer_segments, compute_playback_bounds, AnswerSegment; from src.semantic_search import load_model, embed_documents, embed_query, search_top_k; from src.exporters import build_export_payload, serialize_export; print('All imports OK')"
```

- 전체 테스트 통과
- 모든 공개 인터페이스 import 성공

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md §2 디렉터리 구조와 실제 파일이 일치하는가?
   - ADR에서 결정한 기술 스택을 벗어나지 않았는가?
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가?
   - README에 실제 자격 증명이 포함되어 있지 않은가?
3. 결과에 따라 `phases/0-mvp/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 새 기능을 추가하지 마라. 이유: 이 step은 통합 검증과 정비만 담당한다.
- 기존 모듈의 인터페이스를 변경하지 마라. 이유: 이전 step에서 확정된 시그니처다. 버그 수정만 허용한다.
- README에 실제 자격 증명이나 토큰을 넣지 마라.
- ARCHITECTURE.md에 없는 파일을 임의로 생성하지 마라.
- MVP 제외 사항(자동 평가, 검색 기록 등)을 묵시적으로 추가하지 마라.
- 기존 테스트를 삭제하지 마라. 실패하는 테스트는 수정하되 삭제하지 않는다.
