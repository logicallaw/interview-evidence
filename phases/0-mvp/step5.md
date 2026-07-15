# Step 5: streamlit-app

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` — §3 `app.py` 책임, §4 전체 데이터 흐름, §5 세션 상태, §6 오류와 재시도, §7 캐시 전략
- `/docs/PRD.md` — §4 핵심 사용자 흐름, FR-1~FR-8 전체 기능 요구사항, §6 오류 및 복구
- `/docs/UI_GUIDE.md` — 전체 내용 (depth 구조, 색상, 문구, 금지 패턴)
- `/docs/ADR.md` — ADR-002 세션 상태 라우팅, ADR-009 ±3초 재생, ADR-015 3-depth UX, ADR-016 색상 시스템
- `/src/rtzr_client.py` — Step 1 산출물: 인증, 전사 요청, 상태 조회, 정규화 구조
- `/src/segments.py` — Step 2 산출물: 화자 추출, 대표 발화, 세그먼트 구성, 재생 경계
- `/src/semantic_search.py` — Step 3 산출물: 모델 로드, 임베딩, Top K 검색
- `/src/exporters.py` — Step 4 산출물: export payload, JSON 직렬화
- `/.env.example` — 환경 변수 이름

이전 step에서 만들어진 모든 모듈 코드를 꼼꼼히 읽고, 함수 시그니처와 반환 타입을 정확히 파악한 뒤 작업하라.

## 작업

### `app.py` 구현

Streamlit 앱의 표현 계층과 오케스트레이션을 구현한다. 이 파일은 사용자 입력 수집, `st.session_state` 관리, 화면 렌더링만 담당한다. 도메인 로직은 `src/` 모듈을 호출한다.

#### 전체 구조

```python
import streamlit as st
from dotenv import load_dotenv
# src 모듈 import
# ...

def main():
    load_dotenv()
    st.set_page_config(page_title="Interview Evidence", layout="wide")
    inject_custom_css()
    check_prerequisites()
    init_session_state()

    render_depth_indicator()

    depth = st.session_state.current_depth
    if depth == "audio_setup":
        render_audio_setup()
    elif depth == "speaker_review":
        render_speaker_review()
    elif depth == "evidence_search":
        render_evidence_search()

if __name__ == "__main__":
    main()
```

#### 사전 조건 확인 (`check_prerequisites`)

- `.env`에서 `RTZR_CLIENT_ID`, `RTZR_CLIENT_SECRET`이 설정되어 있는지 확인한다.
- 없으면 `.env` 설정 방법을 안내하고 `st.stop()`한다.
- 자격 증명 값 자체는 화면에 출력하지 않는다.

#### 모델 로드

- `@st.cache_resource`로 `semantic_search.load_model()`을 래핑한다.
- 모델 캐시가 없으면 (`OSError` 또는 관련 예외) `python scripts/prepare_model.py` 실행 안내를 표시하고 검색 기능을 비활성화한다. 앱 자체는 멈추지 않는다 (Depth 1, 2는 사용 가능).
- MPS 실패 시 CPU 폴백 메시지를 `st.info`로 표시한다.

#### 세션 상태 초기화 (`init_session_state`)

최소한 다음 키를 관리한다:

| 키                      | 초기값          | 설명                   |
| ----------------------- | --------------- | ---------------------- |
| `current_depth`         | `"audio_setup"` | 현재 화면              |
| `audio_file`            | `None`          | 업로드된 파일 객체     |
| `audio_bytes`           | `None`          | 음원 바이트            |
| `audio_filename`        | `None`          | 파일명                 |
| `audio_duration_sec`    | `None`          | 음원 길이 (초)         |
| `transcribe_id`         | `None`          | RTZR 작업 ID           |
| `transcription_status`  | `None`          | 전사 상태              |
| `utterances`            | `None`          | 정규화된 발화 리스트   |
| `speakers`              | `None`          | 고유 화자 리스트       |
| `candidate_speaker`     | `None`          | 선택된 지원자 화자     |
| `segments`              | `None`          | AnswerSegment 리스트   |
| `doc_embeddings`        | `None`          | 답변 임베딩            |
| `query`                 | `None`          | 현재 질의              |
| `search_results`        | `None`          | Top 3 결과             |
| `selected_result_index` | `None`          | 상세 layer에 열린 결과 |
| `rtzr_token`            | `None`          | RTZR 인증 토큰         |
| `device_info`           | `None`          | 모델 장치 정보         |

#### Depth 표시 (`render_depth_indicator`)

- 상단에 3개 depth 이름을 가로로 표시한다: `음성 준비`, `화자 확인`, `근거 찾기`.
- 현재 depth는 스카이블루(`#0284C7`)로 강조하고 아래에 얇은 선을 표시한다.
- 나머지는 회색 텍스트로 표시한다.
- `st.markdown`과 CSS로 구현한다. 완료 퍼센트, stepper, 체크마크는 사용하지 않는다.

#### Depth 1: 음성 준비 (`render_audio_setup`)

- `st.file_uploader`로 음성 파일 1개를 받는다.
- 파일이 선택되면 `audio_bytes`, `audio_filename`을 세션에 저장한다.
- 음원 길이를 WAV 헤더에서 계산한다 (wave 모듈 사용). WAV가 아니면 길이를 None으로 두고 진행한다.
- `전사 시작` 버튼을 표시한다.
- 버튼 클릭 시:
  1. `rtzr_client.authenticate()`로 토큰 획득
  2. `rtzr_client.create_transcription()`으로 전사 요청
  3. `transcribe_id`를 세션에 저장
  4. 폴링 시작: `time.sleep(5)` + `st.rerun()` 패턴 또는 `st.status`/`st.spinner`와 while 루프로 5초 간격 폴링
  5. 완료 시 `utterances`를 세션에 저장하고 `current_depth`를 `"speaker_review"`로 변경
- 진행 중 상태를 `st.spinner` 또는 `st.status`로 표시한다.
- `transcribe_id`가 있고 완료되지 않은 경우 `조회 재개` 경로를 제공한다.
- 새 파일 선택 시 전사 이후 상태 전체를 무효화한다.

RTZR 폴링 핵심 규칙:

- 기본 5초 간격
- 네트워크 오류, 429, 500은 백오프 후 같은 ID 재조회
- 60분 제한 도달 시 `transcribe_id`를 보존하고 자동 폴링 중단, 재개 경로 제공
- `failed` 상태는 안전한 오류 메시지 표시 + 새 전사 안내

#### Depth 2: 화자 확인 (`render_speaker_review`)

- `이전` 버튼으로 `audio_setup`으로 돌아갈 수 있다 (전사 결과 유지).
- `segments.get_unique_speakers()`로 화자 추출.
- `segments.validate_speaker_count()`로 2명 검증:
  - 2명이 아니면 전체 타임라인만 표시하고 `화자가 정확히 두 명이 아닙니다` 안내. 화자 선택과 검색 비활성화.
- 각 화자에 대해 `segments.pick_representative_utterances()`로 대표 발화 2~3개를 표시한다.
- 대표 발화 아래에 `지원자로 선택` 버튼을 화자별로 제공한다.
- 선택 시:
  1. `candidate_speaker`를 세션에 저장
  2. `segments.build_answer_segments()`로 답변 구간 구성
  3. 모델이 로드되어 있으면 `semantic_search.embed_documents()`로 searchable 구간 임베딩
  4. `current_depth`를 `"evidence_search"`로 변경
- 화자가 바뀌면 세그먼트, 임베딩, 검색 결과, 상세 상태를 무효화한다.
- 전체 타임라인을 expander 또는 별도 영역에서 확인할 수 있게 한다 (화자, 시각, 텍스트).

#### Depth 3: 근거 찾기 (`render_evidence_search`)

- `이전` 버튼으로 `speaker_review`로 돌아갈 수 있다 (전사 결과, 대표 발화 유지).
- `st.text_input` 또는 `st.text_area`로 평가 기준 입력을 받는다.
- `관련 답변 찾기` 버튼을 표시한다.
- 버튼 클릭 시:
  1. `semantic_search.embed_query()`로 질의 임베딩
  2. `semantic_search.search_top_k()`로 Top 3 검색
  3. 결과를 세션에 저장
- 결과 면책 문구를 표시한다:
  > 입력한 기준과 의미가 가까운 순서로 표시했습니다. 필요한 판단은 원문과 원음을 확인한 뒤 내려주세요.
- 각 결과를 카드 형태로 표시한다:
  - 순위 번호 (1, 2, 3)
  - 답변 텍스트 (처음 100~150자 + 말줄임)
  - 시작~종료 시각 (MM:SS 형식)
  - `전사 문맥 보기` 버튼 → 상세 layer 열기
- 질의 변경 시 질의 임베딩과 Top 3만 갱신한다. 답변 임베딩은 재사용한다.
- `현재 검색 결과 내려받기` 버튼:
  - `exporters.build_export_payload()` → `exporters.serialize_export()` → `st.download_button`

#### 상세 Layer

Depth 3 안에서 결과 하나를 선택하면 상세 정보를 표시한다. 별도 페이지가 아니라 같은 화면의 확장 영역이다.

- 선택한 답변의 전체 텍스트
- 직전 면접관 발화 (문맥 제공)
- 오디오 플레이어: `st.audio(audio_bytes, start_time=start_sec, end_time=end_sec)`
  - `segments.compute_playback_bounds()`로 계산한 경계 사용
  - `이 구간 듣기` 레이블
- 접을 수 있는 검색 정보 (`st.expander`):
  - 코사인 유사도 (소수점 그대로)
  - 원본 발화 인덱스
- `닫기` 버튼으로 상세 layer를 닫을 수 있다 (검색 결과는 유지).

#### CSS 주입 (`inject_custom_css`)

`st.markdown`으로 커스텀 CSS를 주입한다:

- 기본 색상 토큰:
  - main: `#0284C7`
  - hover: `#0369A1`
  - selection background: `#E0F2FE`
  - border: `#E2E8F0`
  - text: `#0F172A`
- 주요 버튼에 스카이블루 적용
- 색상, 게이지, 메달, 별로 결과 품질을 표현하지 않는다

#### 상태 무효화 규칙

반드시 다음 규칙을 따른다:

| 이벤트                      | 무효화 대상                                                                                         |
| --------------------------- | --------------------------------------------------------------------------------------------------- |
| 새 파일 선택 / 새 전사 시작 | 전사 이후 상태 전체 (utterances, speakers, candidate, segments, embeddings, query, results, detail) |
| 지원자 화자 변경            | segments, doc_embeddings, query, search_results, selected_result_index                              |
| 새 질의 제출                | search_results, selected_result_index                                                               |
| 상세 layer 닫기             | selected_result_index만 (query와 results 유지)                                                      |
| depth 이동 (이전)           | 전사 결과 유지, depth만 변경                                                                        |

#### 고정 문구 (UI_GUIDE.md 기준)

- 앱 제목 영역: `"면접에서 다시 확인할 답변을 찾아보세요."`
- 면책 문구: `"지원자를 자동 평가하거나 점수를 매기지 않습니다."`
- 결과 안내: `"입력한 기준과 의미가 가까운 순서로 표시했습니다. 필요한 판단은 원문과 원음을 확인한 뒤 내려주세요."`
- 버튼: `전사 시작`, `지원자로 선택`, `관련 답변 찾기`, `이 구간 듣기`, `전사 문맥 보기`, `현재 검색 결과 내려받기`

## Acceptance Criteria

이 step은 Streamlit UI이므로 자동화된 AC 커맨드가 제한적이다.

```bash
python -c "import app"
python -m pytest tests/ -v
```

- `import app`이 Streamlit 실행 없이 문법 에러를 발생시키지 않는다.
- 기존 모든 단위 테스트가 통과한다.
- 수동 검증: `streamlit run app.py`로 다음을 확인한다:
  - 3 depth 표시와 전환
  - 파일 업로드와 전사 진행
  - 화자 대표 발화와 선택
  - 질의 입력과 Top 3 결과
  - 상세 layer의 오디오 재생과 문맥
  - JSON 다운로드
  - 색상과 문구 일관성

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `app.py`가 RTZR HTTP 세부 구현, 원본 JSON 해석, 임베딩 계산, export 필드 선택을 직접 하지 않는가?
   - 도메인 로직은 `src/` 모듈 호출로 처리하는가?
   - UI_GUIDE.md의 금지 문구(`AI 분석`, `인사이트 생성` 등)를 사용하지 않는가?
   - 색상 토큰이 UI_GUIDE.md와 일치하는가?
   - 세 depth를 한 화면에 동시에 노출하지 않는가?
   - `st.session_state`로 depth를 전환하고 별도 multipage 라우팅을 사용하지 않는가?
3. 결과에 따라 `phases/0-mvp/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 도메인 로직(발화 병합, 유사도 계산, export 필드 선택)을 app.py에 직접 구현하지 마라. 이유: `src/` 모듈에 있다.
- `AI 분석`, `인사이트 생성`, `최적의 답변`, `높은 관련성`, `지원자 적합도`, `AI 점수`라는 문구를 사용하지 마라. 이유: CLAUDE.md CRITICAL UI 규칙이다.
- 색상, 게이지, 메달, 별, 점수로 결과 품질을 표현하지 마라. 이유: 평가 도구가 아니다.
- 세 depth를 한 화면에 동시에 노출하지 마라. 이유: ADR-015에서 분리로 결정했다.
- `st.Page`, `st.navigation` 등 Streamlit multipage 라우팅을 사용하지 마라. 이유: ADR-002에서 세션 상태 전환으로 결정했다.
- 검색 기록을 누적하지 마라. 이유: 현재 질의와 현재 결과만 유지한다.
- 앱 실행 중 모델을 다운로드하지 마라. 이유: `local_files_only=True`가 기본이다.
- fixture 선택 경로나 샘플 모드를 만들지 마라. 이유: ADR-011에서 금지했다.
- 사용자 결과를 서버에 자동 저장하지 마라. 이유: 메모리 기반 다운로드만 허용한다.
- 기존 테스트를 깨뜨리지 마라.
