# Interview Evidence 아키텍처

## 1. 설계 목표

아키텍처는 다음 한 줄의 흐름을 가장 적은 구성으로 안정적으로 지원해야 한다.

```text
Depth 1 음성 준비 → Depth 2 화자 확인 → Depth 3 근거 찾기 → 결과 상세 layer
```

핵심 원칙은 다음과 같다.

- Streamlit은 얇은 표현 계층으로 유지한다.
- 화면은 별도 페이지 라우팅 없이 세션 상태로 3개 depth를 전환한다.
- 외부 API, 도메인 규칙과 직렬화 로직은 UI에서 분리한다.
- 실제 RTZR 응답과 테스트 fixture는 같은 파서와 후처리 경로를 통과한다.
- 사용자 음원, 전체 전사문과 검색 기록을 영속화하지 않는다.
- 확정되지 않은 휴리스틱과 MVP 외 기능을 추가하지 않는다.

## 2. 목표 디렉터리 구조

```text
interview-evidence/
├── app.py                         # Streamlit 렌더링과 세션 오케스트레이션
├── scripts/
│   └── prepare_model.py           # 모델 다운로드·로드·임베딩 사전 검증
├── src/
│   ├── __init__.py
│   ├── rtzr_client.py             # 인증, 전사 요청, 폴링, 응답 정규화
│   ├── segments.py                # 화자 검증과 답변 구간 구성
│   ├── semantic_search.py         # 모델 로드, 임베딩, 코사인 Top K
│   └── exporters.py               # 허용 필드 기반 JSON payload와 직렬화
├── tests/
│   ├── fixtures/
│   │   └── rtzr_completed.json    # 비식별 합성 데이터의 완료 응답
│   ├── test_rtzr_client.py
│   ├── test_segments.py
│   ├── test_semantic_search.py
│   └── test_exporters.py
├── public/
│   └── audio/
│       ├── interview-sample.wav
│       └── interview-sample.txt   # 내용 확인용 참고 전사, 정답 데이터 아님
├── docs/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

이 구조는 목표 상태다. 파일이 아직 없다면 해당 기능을 구현하는 단계에서만 생성한다.

## 3. 계층과 책임

### `app.py`: 표현 및 오케스트레이션

담당한다.

- 페이지 구성과 컴포넌트 렌더링
- 현재 depth에 맞는 화면만 렌더링하고 상단 위치 표시 제공
- 업로드 파일과 사용자 입력 수집
- 전사 시작·조회 재개·화자 선택·검색·결과 선택 이벤트 처리
- `st.session_state` 갱신
- 진행, 빈 상태, 경고와 오류 표시
- 화자별 대표 발화, 결과 상세 layer, 공용 오디오 플레이어와 다운로드 버튼 연결
- `docs/UI_GUIDE.md`에 정의된 고정 문구와 색상 토큰 적용

담당하지 않는다.

- RTZR HTTP 요청 세부 구현
- 원본 RTZR JSON 직접 해석
- 답변 병합과 최소 글자 수 판정
- 임베딩 프롬프트와 유사도 계산
- 내보내기 필드 선택과 JSON 조립

### `src/rtzr_client.py`: RTZR 어댑터

담당한다.

- 자격 증명으로 인증 토큰 획득
- 전사 요청 구성과 음성 업로드
- `transcribe_id` 기반 상태 조회
- 상태와 오류 코드 정규화
- 완료 응답의 필수 구조 검증
- 요청과 폴링에 서로 다른 재시도 정책 적용

외부 응답을 있는 그대로 UI에 노출하지 않고 최소한 다음 정보로 정규화한다.

```text
TranscriptionJob
  id
  status: transcribing | completed | failed
  utterances[]
  error_code?
  error_message?

Utterance
  index
  speaker
  start_at_ms
  duration_ms
  text
```

실제 구현은 dataclass, TypedDict 또는 검증 함수 중 프로젝트 규모에 맞는 가장 단순한 방식을 선택한다. 단일 용도의 복잡한 스키마 프레임워크는 추가하지 않는다.

### `src/segments.py`: 도메인 규칙

담당한다.

- 발화 정렬
- 고유 화자 목록 추출과 정확히 두 명인지 검증
- 지원자 화자의 연속 발화 병합
- 구간 시작·종료 시각 계산
- 검색 대상 최소 글자 수 판정
- 오디오 재생 경계 계산

핵심 입력과 출력 형태는 다음 개념을 보존한다.

```text
AnswerSegment
  text
  start_at_ms
  end_at_ms
  source_utterance_indexes[]
  searchable
```

세그먼트 모듈은 Streamlit, HTTP와 모델 라이브러리에 의존하지 않는 순수 로직으로 작성한다.

### `src/semantic_search.py`: 로컬 의미 검색

담당한다.

- 캐시된 `google/embeddinggemma-300m` 로드
- MPS 선택과 CPU 대체
- 답변 문서 임베딩 생성
- 질의 임베딩 생성
- 코사인 유사도 내림차순 정렬과 최대 3개 반환

검색 계약은 다음과 같다.

```text
query text
  → prompt_name="Retrieval-query"

answer segment text
  → prompt_name="Retrieval-document"

both
  → normalize_embeddings=True
  → cosine similarity
  → descending sort
  → first min(3, searchable_count)
```

절대 점수 임계값과 높음·보통·낮음 구간은 정의하지 않는다.

### `src/exporters.py`: 제한된 내보내기

담당한다.

- 현재 질의와 현재 검색 결과로 export payload 생성
- 허용 필드만 선택
- UTF-8 JSON bytes 직렬화

전사 전체나 원본 API 응답을 인자로 받아 그대로 덤프하는 범용 exporter를 만들지 않는다. 개인정보 누출 표면을 불필요하게 넓히기 때문이다.

### `scripts/prepare_model.py`: 설치 전 검증

담당한다.

1. `.env`에서 `HF_TOKEN` 확인
2. EmbeddingGemma 접근 가능 여부 확인
3. Hugging Face 캐시에 모델 다운로드
4. 모델 실제 로드
5. 짧은 질의·문서 임베딩 생성
6. 사용한 장치와 성공 여부 출력

모델 파일은 프로젝트 폴더에 복사하거나 Git에 포함하지 않는다.

## 4. 데이터 흐름

### 4.1 앱 시작과 사전 조건

```text
.env
  → 자격 증명 존재 여부 확인
Hugging Face cache
  → local_files_only 모델 로드 가능 여부 확인
  → 불충족 시 준비 방법 표시
```

앱은 사전 조건 오류를 화면에 표시할 수 있지만 비밀 값 자체는 렌더링하거나 로그에 남기지 않는다.

### 4.2 전사 흐름

```text
UploadedFile
  → app.py 입력 검증
  → rtzr_client.authenticate()
  → rtzr_client.create_transcription(file, config)
  → transcribe_id를 session_state에 즉시 저장
  → rtzr_client.get_transcription(transcribe_id), 기본 5초 폴링
  → completed response 검증·정규화
  → normalized utterances를 session_state에 저장
  → current_depth를 speaker_review로 변경
  → 화자 확인 화면 렌더링
```

전사 설정은 다음 값으로 고정한다.

```text
model_name = sommers
domain = GENERAL
use_diarization = true
spk_count = 2
use_word_timestamp = false
use_itn = true
use_disfluency_filter = true
use_paragraph_splitter = true
paragraph_splitter.max = 130
```

키워드 부스팅이 나중에 추가되더라도 빈 입력은 요청에 불필요한 `keywords`를 만들지 않는다.

### 4.3 화자 선택과 답변 구간

```text
normalized utterances
  → unique speakers
  → count == 2 ? speaker selection enabled : search disabled
  → 각 화자의 짧지 않은 대표 발화 2~3개 선택
  → 화자 선택 카드 렌더링
  → candidate speaker selected
  → sort by start_at_ms
  → merge consecutive candidate utterances
  → preserve source indexes and time bounds
  → normalized character count >= 10인 구간만 searchable
  → document embeddings 준비
  → current_depth를 evidence_search로 변경
```

공백과 문장부호 제거는 검색 가능 여부를 판단할 때만 사용한다. 사용자에게 표시하고 임베딩할 텍스트는 원문을 유지한다.

### 4.4 의미 검색

```text
searchable answer segments
  → document embeddings 1회 계산
  → session_state에 현재 전사·지원자 선택과 연결해 캐시

query submit
  → query embedding 계산
  → cosine similarity
  → Top 3
  → 현재 결과 교체
```

지원자 선택이 바뀌면 답변 구간과 문서 임베딩을 무효화한다. 새 음성을 업로드하거나 새 전사를 시작하면 화자 선택, 세그먼트, 임베딩, 질의, 결과와 플레이어 선택을 모두 무효화한다.

### 4.5 원음 재생과 다운로드

```text
selected SearchResult
  → Depth 3 안에서 detail layer 열기
  → 직전 면접관 발화와 선택 답변 문맥 구성
  → start_sec = max(0, floor(start_at_ms / 1000) - 3)
  → end_sec = min(audio_duration, ceil(end_at_ms / 1000) + 3)
  → st.audio(original bytes, start_time, end_time)

current query + Top 3
  → build_export_payload()
  → UTF-8 JSON bytes
  → st.download_button
  → browser download
```

오디오 바이트는 사용자 세션에서 재생에 사용하지만 파일로 자동 저장하지 않는다.

## 5. 세션 상태

MVP에서는 별도 상태 관리 라이브러리나 데이터베이스를 사용하지 않고 `st.session_state`를 사용한다. 구현 키 이름은 달라질 수 있지만 다음 상태 묶음을 구분한다.

| 상태 | 내용 | 무효화 조건 |
|---|---|---|
| 화면 depth | `audio_setup`, `speaker_review`, `evidence_search` | 명시적 이전·다음 이동 또는 새 전사 |
| 입력 | 업로드 파일명, 음원 bytes, 길이 | 새 파일 선택 |
| 전사 작업 | `transcribe_id`, 상태, 안전한 오류 | 새 전사 시작 |
| 전사 결과 | 정규화 발화, 고유 화자 | 새 전사 시작 |
| 화자 확인 | 화자별 대표 발화, 지원자 화자 ID | 전사 결과 변경 |
| 검색 인덱스 | 답변 구간, 문서 임베딩, 장치 | 역할 또는 전사 변경 |
| 현재 검색 | 질의, Top 3 | 새 질의 제출 또는 검색 인덱스 변경 |
| 결과 상세 | 선택 결과, 문맥 발화와 재생 경계 | 검색 결과 변경 |

정상 진행은 다음 순서를 따른다.

```text
audio_setup
  EMPTY → FILE_SELECTED → SUBMITTING → TRANSCRIBING → COMPLETED
  → speaker_review
  SPEAKER_PREVIEW → SPEAKER_SELECTED → INDEXING
  → evidence_search
  SEARCH_READY → RESULTS_READY → DETAIL_OPEN
```

이전 depth 이동은 허용하지만 다음 규칙을 지킨다.

- `evidence_search → speaker_review`: 전사 결과와 대표 발화는 유지한다.
- 지원자 화자 변경: 세그먼트, 문서 임베딩, 현재 검색과 결과 상세를 무효화한다.
- `speaker_review → audio_setup`: 기존 전사 결과는 사용자가 새 파일이나 새 전사를 명시적으로 시작하기 전까지 유지한다.
- 새 파일 선택 또는 새 전사 시작: 전사 결과 이후의 모든 상태를 무효화한다.
- 결과 상세 layer를 닫아도 질의와 Top 3는 유지한다.
- URL deep link와 새로고침 뒤 상태 복원은 구현하지 않는다.

오류는 별도 최종 상태가 아니라 사용자가 복구할 수 있는 현재 단계의 표시로 다룬다. 단, RTZR가 `failed`를 반환한 작업은 같은 ID로 완료 상태가 될 것이라 가정하지 않는다.

## 6. 오류와 재시도 경계

### 전사 생성 요청

- 인증 실패와 유효하지 않은 파일은 재시도하지 않는다.
- `429 A0002`는 2초, 4초, 8초 후 최대 세 번 재시도한다.
- 네트워크 타임아웃은 자동 재시도하지 않는다. 요청 접수 여부를 알 수 없어 중복 전사를 만들 수 있기 때문이다.

### 상태 폴링

- 기본 간격은 5초다.
- 네트워크 오류, 429, 500은 백오프 후 동일 ID를 다시 조회한다.
- 최대 60분 후에는 ID를 보존하고 자동 폴링만 멈춘다.
- 사용자가 조회 재개를 선택하면 저장된 ID로 이어서 조회한다.

### 모델

- 모델 미준비는 런타임 다운로드로 해결하지 않는다.
- MPS 실패 시 같은 작업을 CPU로 한 번만 대체한다.
- CPU에서도 실패하면 원인과 준비 스크립트 안내를 표시하고 검색을 중단한다.

오류 메시지는 자격 증명, 토큰, 원본 요청 헤더와 전체 API 응답을 포함하지 않는다.

## 7. 캐시 전략

- 모델 인스턴스: `st.cache_resource`
- 답변 임베딩: 현재 전사 결과와 지원자 화자 선택에 종속된 세션 상태
- 질의 임베딩: 제출할 때마다 계산
- RTZR 인증 토큰: 유효 범위 안에서 클라이언트 내부 재사용 가능하나 영속 저장하지 않음
- 원본 RTZR 완료 응답: 앱 세션에서 필요한 정규화가 끝나면 UI가 의존하지 않게 함

전역 디스크 캐시나 사용자 간 공유 캐시는 MVP에서 만들지 않는다.

## 8. 테스트 전략

### 단위 테스트

- 완료 응답 필수 필드 검증과 정규화
- 발화 정렬과 고유 화자 추출
- 연속 지원자 발화 병합
- 다른 화자 및 맞장구에서 구간 종료
- 10자 미만 검색 제외와 원문 보존
- 종료 시각 계산
- 음원 시작·끝 경계에서 전후 3초 보정
- 유사도 내림차순과 결과 수 0·1·2·3 이상 처리
- export 허용 필드와 UTF-8 직렬화
- 오류 유형별 재시도 여부와 횟수

### fixture 원칙

- `tests/fixtures/rtzr_completed.json`은 합성 음원의 비식별 완료 응답만 담는다.
- 실제 자격 증명, 작업 소유자 정보, 생성 시각 등 불필요한 식별자는 제거한다.
- 앱에 fixture 선택 경로나 샘플 모드를 만들지 않는다.
- fixture가 실제 응답과 동일한 파싱 함수를 통과하는지 검증한다.

### 수동 통합 검증

- 실제 자격 증명으로 합성 WAV 전사
- 전사 진행과 완료 상태 표시
- 두 화자 및 타임라인 확인
- 대표 질의의 기대 답변이 Top 3에 포함되는지 확인
- 세 결과의 재생 경계 확인
- 다운로드 JSON의 필드와 한글 인코딩 확인
- 모델 미준비, 잘못된 화자 수, RTZR 실패의 화면 복구 확인

## 9. 보안과 데이터 수명

| 데이터 | 위치 | 수명 | 내보내기 |
|---|---|---|---|
| RTZR 자격 증명 | 로컬 `.env` | 사용자가 삭제할 때까지 | 금지 |
| HF 토큰 | 로컬 `.env` | 사용자가 삭제할 때까지 | 금지 |
| 업로드 음원 | Streamlit 세션 메모리 | 세션/파일 교체까지 | 금지 |
| `transcribe_id` | Streamlit 세션 상태 | 작업/세션까지 | 기본 export에서 제외 |
| 정규화 전사 | Streamlit 세션 상태 | 세션/새 전사까지 | 전체 export 금지 |
| 답변 임베딩 | Streamlit 세션 상태 | 역할/전사 변경까지 | 금지 |
| 현재 Top 3 | Streamlit 세션 상태 | 새 검색/세션까지 | 허용 필드만 JSON |
| 테스트 fixture | 저장소 | 프로젝트 수명 | 합성·비식별 데이터만 |

`outputs/`는 로컬 디버깅에서 명시적으로 저장할 때만 사용하며 애플리케이션의 정상 데이터 흐름에는 포함하지 않는다.

## 10. 아키텍처 비목표

- 서버·클라이언트 분리와 별도 REST API
- 데이터베이스와 사용자 계정
- 작업 큐와 백그라운드 워커
- 여러 사용자 또는 여러 지원자 데이터 모델
- 실시간 스트리밍 STT
- 플러그인형 임베딩 모델 추상화
- 범용 전사 export 프레임워크
- 자동 평가 파이프라인

이 항목들은 현재 요구사항을 해결하는 데 필요하지 않으며 MVP 복잡도와 개인정보 위험만 늘린다.
