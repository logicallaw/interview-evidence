# Step 1: rtzr-client

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` — §3 `src/rtzr_client.py` 책임, §4.2 전사 흐름, §6 오류와 재시도 경계
- `/docs/ADR.md` — ADR-001 파일 기반 STT, ADR-011 fixture 전용, ADR-014 오류별 재시도
- `/docs/PRD.md` — FR-2 음성 업로드와 RTZR 전사, §6 오류 및 복구 요구사항
- `/src/__init__.py` — Step 0에서 생성된 빈 패키지
- `/tests/conftest.py` — Step 0에서 생성된 공용 설정
- `/.env.example` — 환경 변수 이름 확인

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

### 1. `src/rtzr_client.py` 구현

RTZR 일반 STT API를 래핑하는 모듈을 구현한다.

#### 도메인 구조

```python
@dataclass
class Utterance:
    index: int
    speaker: str
    start_at_ms: int
    duration_ms: int
    text: str

@dataclass
class TranscriptionJob:
    id: str
    status: str          # "transcribing" | "completed" | "failed"
    utterances: list      # list[Utterance], completed일 때만 채워짐
    error_code: str | None
    error_message: str | None
```

구현 형태(dataclass, TypedDict 등)는 자유롭되 위 필드와 의미를 보존해야 한다.

#### 인증

```python
def authenticate(client_id: str, client_secret: str) -> str:
    """RTZR OAuth 토큰을 획득한다. 실패 시 예외를 발생시킨다."""
```

- POST `https://openapi.vito.ai/v1/authenticate`
- `client_id`, `client_secret`를 form data로 전송
- 응답에서 `access_token`을 반환

#### 전사 요청

```python
def create_transcription(token: str, file_bytes: bytes, filename: str) -> str:
    """전사 요청을 생성하고 transcribe_id를 반환한다."""
```

- POST `https://openapi.vito.ai/v1/transcribe`
- Authorization: `Bearer {token}`
- multipart/form-data: `file` (파일 바이트), `config` (JSON 문자열)
- config는 다음 값으로 고정:

```json
{
  "model_name": "sommers",
  "domain": "GENERAL",
  "use_diarization": true,
  "diarization": { "spk_count": 2 },
  "use_word_timestamp": false,
  "use_itn": true,
  "use_disfluency_filter": true,
  "use_paragraph_splitter": true,
  "paragraph_splitter": { "max": 130 }
}
```

- **재시도 정책**: `429` 응답이고 에러 코드가 `A0002`이면 2초, 4초, 8초 간격으로 최대 3회 재시도한다. 그 외 오류와 네트워크 타임아웃은 재시도하지 않는다.
- 응답에서 `id` 필드를 반환한다.

#### 상태 조회

```python
def get_transcription(token: str, transcribe_id: str) -> TranscriptionJob:
    """전사 상태를 조회하고 정규화된 TranscriptionJob을 반환한다."""
```

- GET `https://openapi.vito.ai/v1/transcribe/{transcribe_id}`
- Authorization: `Bearer {token}`
- 응답 구조를 정규화하여 `TranscriptionJob`으로 반환
- `status`가 `completed`일 때 `utterances` 필수 구조 검증:
  - `utterances` 배열 존재
  - 각 항목에 `spk`, `start_at`, `duration`, `msg` 필드 존재
  - 인덱스는 배열 순서에서 자동 부여 (0-based)

#### 응답 검증

```python
def _validate_completed_response(data: dict) -> list[Utterance]:
    """완료 응답의 utterances를 검증하고 Utterance 리스트로 변환한다."""
```

- `results.utterances` 경로에서 발화 배열을 추출한다.
- 각 발화의 필수 필드(`spk`, `start_at`, `duration`, `msg`)가 없으면 ValueError를 발생시킨다.
- `start_at`과 `duration`은 밀리초 정수다.

#### 핵심 규칙

- 오류 메시지에 자격 증명, 토큰, 원본 요청 헤더, 전체 API 응답 본문을 포함하지 않는다.
- `requests` 라이브러리를 사용한다. `httpx`, `aiohttp` 등을 추가하지 않는다.
- 폴링 로직(루프, sleep)은 이 모듈에 넣지 않는다. 단일 조회만 담당하고 폴링은 app.py에서 처리한다.
- 키워드 부스팅 파라미터를 config에 넣지 않는다 (MVP 제외).

### 2. `tests/fixtures/rtzr_completed.json` 생성

합성 면접 데이터의 비식별 완료 응답 fixture를 만든다.

- `/public/audio/interview-sample.txt`의 내용을 참고하여 RTZR 완료 응답 형태로 구성한다.
- 실제 RTZR API 응답 구조를 따른다:

```json
{
  "id": "test-transcribe-id",
  "status": "completed",
  "results": {
    "utterances": [
      {
        "spk": 0,
        "start_at": 0,
        "duration": 18000,
        "msg": "발화 텍스트"
      }
    ]
  }
}
```

- `spk`는 0과 1 두 화자만 사용한다.
- `start_at`과 `duration`은 `interview-sample.txt`의 타임스탬프를 밀리초로 변환한다.
- 실제 자격 증명, 작업 소유자 정보, 생성 시각 등 식별 메타데이터는 포함하지 않는다.
- 참석자 1 → spk 0, 참석자 2 → spk 1로 매핑한다.

### 3. `tests/test_rtzr_client.py` 구현

단위 테스트를 작성한다. 실제 HTTP 호출은 하지 않고 `unittest.mock`으로 `requests` 응답을 모킹한다.

테스트할 항목:

- **정규화**: 완료 응답 fixture를 `_validate_completed_response`에 통과시켜 올바른 `Utterance` 리스트가 나오는지 확인
- **필수 필드 누락**: `spk`, `start_at`, `duration`, `msg` 중 하나가 없으면 ValueError 발생
- **utterances 빈 배열**: 빈 발화 목록도 유효한 완료 응답으로 처리
- **인증 성공**: mock 응답에서 `access_token` 추출
- **인증 실패**: 401 응답 시 예외 발생
- **전사 요청 성공**: mock 응답에서 `id` 추출
- **429 A0002 재시도**: 처음 두 번 429, 세 번째 성공 → 최종 성공
- **429 A0002 최대 초과**: 4번 연속 429 → 예외 발생
- **전사 조회 성공**: completed 상태의 정규화 확인
- **fixture 파싱**: `tests/fixtures/rtzr_completed.json`을 로드해서 `_validate_completed_response`를 통과시키는 테스트

## Acceptance Criteria

```bash
python -m pytest tests/test_rtzr_client.py -v
```

- 모든 테스트가 통과한다.
- 네트워크 호출이나 RTZR 자격 증명 없이 실행된다.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `src/rtzr_client.py`가 ARCHITECTURE.md §3의 rtzr_client 책임만 담당하는가?
   - 폴링 루프가 이 모듈에 포함되어 있지 않은가?
   - Streamlit에 의존하지 않는가?
   - 오류 메시지에 자격 증명이나 토큰이 노출되지 않는가?
   - fixture에 식별 메타데이터가 없는가?
3. 결과에 따라 `phases/0-mvp/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 폴링 루프(while + sleep)를 이 모듈에 넣지 마라. 이유: 폴링은 app.py가 Streamlit 이벤트 루프와 함께 처리한다.
- `httpx`, `aiohttp` 등 추가 HTTP 라이브러리를 도입하지 마라. 이유: `requests`만 사용한다.
- 키워드 부스팅 파라미터를 config에 추가하지 마라. 이유: MVP 제외 사항이다.
- 네트워크 타임아웃을 자동 재시도하지 마라. 이유: 서버 접수 여부를 알 수 없어 중복 전사를 만들 수 있다.
- fixture에 실제 자격 증명이나 식별 가능한 메타데이터를 넣지 마라.
- 기존 테스트를 깨뜨리지 마라.
