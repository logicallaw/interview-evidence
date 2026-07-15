# Step 2: segments

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` — §3 `src/segments.py` 책임, §4.3 화자 선택과 답변 구간
- `/docs/ADR.md` — ADR-003 2인 제한, ADR-004 연속 발화 병합, ADR-005 10자 미만 제외
- `/docs/PRD.md` — FR-3 화자 역할, FR-4 답변 구간 구성, FR-6 근거 원음 재생 경계
- `/src/rtzr_client.py` — Step 1에서 생성된 Utterance, TranscriptionJob 구조 확인
- `/tests/fixtures/rtzr_completed.json` — Step 1에서 생성된 fixture의 발화 데이터 확인
- `/tests/conftest.py` — 공용 fixture 경로

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 작업

### 1. `src/segments.py` 구현

답변 구간 구성과 관련된 순수 도메인 로직을 구현한다. 이 모듈은 Streamlit, HTTP, 모델 라이브러리에 의존하지 않는다.

#### 도메인 구조

```python
@dataclass
class AnswerSegment:
    text: str                        # 연속 발화의 결합 텍스트 (원문 유지)
    start_at_ms: int                 # 첫 발화의 start_at_ms
    end_at_ms: int                   # 마지막 발화의 start_at_ms + duration_ms
    source_utterance_indexes: list   # list[int], 원본 발화 인덱스
    searchable: bool                 # 공백·문장부호 제거 후 10자 이상이면 True
```

#### 함수 시그니처

```python
def get_unique_speakers(utterances: list) -> list[str]:
    """발화에서 고유 화자 목록을 추출한다. 등장 순서를 유지한다."""

def validate_speaker_count(speakers: list[str]) -> bool:
    """고유 화자가 정확히 2명인지 검증한다."""

def pick_representative_utterances(utterances: list, speaker: str, count: int = 3) -> list:
    """특정 화자의 대표 발화를 선택한다.

    선택 기준:
    - 해당 화자의 발화만 필터링
    - start_at_ms 오름차순 정렬
    - 공백·문장부호 제거 후 텍스트가 지나치게 짧은 발화(5자 미만)는 건너뜀
    - 앞에서부터 최대 count개 선택
    - 역할을 자동 추론하지 않는다
    """

def build_answer_segments(utterances: list, candidate_speaker: str) -> list:
    """지원자의 연속 발화를 답변 구간으로 구성한다.

    규칙:
    1. utterances를 start_at_ms 오름차순으로 정렬한다.
    2. candidate_speaker의 연속 발화를 하나의 AnswerSegment로 묶는다.
    3. 다른 화자의 발화가 나오면 현재 구간을 종료한다.
    4. 면접관의 짧은 맞장구도 경계로 처리한다 (맞장구 병합 금지).
    5. text는 연속 발화의 msg를 공백으로 결합한다.
    6. end_at_ms = 마지막 발화의 start_at_ms + duration_ms.
    7. searchable: 공백과 문장부호(re 사용)를 제거한 텍스트가 10자 이상이면 True.
    8. searchable이 False여도 리스트에 포함한다 (타임라인 표시용).
    """

def compute_playback_bounds(start_at_ms: int, end_at_ms: int, audio_duration_sec: float) -> tuple[int, int]:
    """오디오 재생 경계를 계산한다.

    반환: (start_sec, end_sec)
    - start_sec = max(0, floor(start_at_ms / 1000) - 3)
    - end_sec = min(audio_duration_sec, ceil(end_at_ms / 1000) + 3)
    - 둘 다 정수(int)로 반환한다.
    """
```

#### 핵심 규칙

- `rtzr_client.py`의 `Utterance` 타입을 import해서 사용한다. 별도 발화 구조를 만들지 않는다.
- 공백·문장부호 제거는 `re.sub(r'[\s\p{P}]', '', text)` 또는 동등한 정규식을 사용한다. `\W`는 한글을 제거하므로 사용하지 않는다. `string.punctuation` 기반도 허용한다.
- 짧은 구간을 앞뒤 구간에 자동 병합하지 않는다.
- `build_answer_segments`는 `utterances` 리스트를 변경하지 않는다 (원본 불변).

### 2. `tests/test_segments.py` 구현

단위 테스트를 작성한다.

테스트할 항목:

- **고유 화자 추출**: 2명 → 등장 순서 유지, 1명/3명 → validate_speaker_count가 False
- **대표 발화 선택**: 짧은 발화 건너뛰기, 최대 count개 반환, 해당 화자만 필터링
- **연속 발화 병합**: 같은 화자 3개 연속 → 1개 AnswerSegment
- **다른 화자에서 구간 종료**: A-A-B-A → 2개 구간
- **맞장구 경계**: 짧은 면접관 발화도 구간을 분리하는지 확인
- **end_at_ms 계산**: 마지막 발화의 `start_at_ms + duration_ms`와 일치
- **10자 미만 제외**: 공백·문장부호 제거 후 9자 → searchable=False, 10자 → searchable=True
- **searchable=False도 리스트에 포함**: 타임라인 표시용으로 제거하지 않음
- **text 결합**: 공백으로 join, 원문 유지 (문장부호 제거 적용 안 함)
- **재생 경계**: 정상 범위, 음원 시작(0초) 경계, 음원 끝 경계
- **빈 발화 리스트**: build_answer_segments에 빈 리스트 → 빈 리스트 반환
- **fixture 기반 테스트**: `rtzr_completed.json`의 발화를 파싱하여 세그먼트를 구성하고, 구간 수와 searchable 여부를 확인

## Acceptance Criteria

```bash
python -m pytest tests/test_segments.py tests/test_rtzr_client.py -v
```

- 모든 테스트(segments + 기존 rtzr_client)가 통과한다.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `src/segments.py`가 Streamlit, requests, torch에 의존하지 않는가?
   - `rtzr_client.py`의 `Utterance`를 재사용하는가?
   - 맞장구 병합 휴리스틱이 없는가?
   - 짧은 구간을 앞뒤에 자동 병합하지 않는가?
3. 결과에 따라 `phases/0-mvp/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 맞장구 병합 휴리스틱을 추가하지 마라. 이유: fixture 검증 없이 추가하면 의도하지 않은 구간 합병이 발생한다.
- 짧은 구간을 앞뒤 답변에 자동 병합하지 마라. 이유: PRD FR-4에서 명시적으로 금지하고 있다.
- 한글 문자를 제거하는 정규식(`\W`)을 searchable 판정에 사용하지 마라. 이유: 한글이 제거되어 글자 수가 줄어든다.
- `Utterance`를 이 모듈에서 새로 정의하지 마라. 이유: `rtzr_client.py`에 이미 있다.
- Streamlit, requests, torch를 import하지 마라. 이유: 순수 도메인 로직이다.
- 기존 테스트를 깨뜨리지 마라.
