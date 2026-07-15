# Step 0: project-setup

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` — 목표 디렉터리 구조(§2)와 계층 책임(§3) 확인
- `/docs/ADR.md` — 기술 스택 결정 확인 (ADR-006 EmbeddingGemma, ADR-007 prepare_model.py 등)
- `/docs/PRD.md` — FR-1 실행 전 준비 요구사항 확인
- `/.env.example` — 환경 변수 목록 확인
- `/.gitignore` — 이미 제외된 경로 확인

## 작업

### 1. `requirements.txt` 생성

프로젝트 루트에 `requirements.txt`를 생성한다. 다음 패키지를 포함한다:

```
streamlit
requests
python-dotenv
sentence-transformers
torch
pytest
```

- 버전 핀은 하지 않는다 (로컬 MVP이므로 최신 호환 버전 사용).
- `transformers`, `numpy` 등 `sentence-transformers`가 끌고 오는 전이 의존성은 명시하지 않는다.

### 2. 디렉터리 구조 생성

ARCHITECTURE.md §2의 목표 구조에 맞게 빈 패키지 파일을 생성한다:

```
src/__init__.py          # 빈 파일
tests/__init__.py        # 빈 파일
tests/fixtures/          # 빈 디렉터리 (다음 step에서 fixture 추가)
```

`src/__init__.py`와 `tests/__init__.py`는 빈 파일로 생성한다. 내용을 넣지 않는다.

### 3. `tests/conftest.py` 생성

```python
"""프로젝트 공용 pytest 설정."""
```

- 이 단계에서는 fixture나 설정 없이 docstring만 넣는다. 이후 step에서 필요한 fixture를 추가한다.
- `tests/fixtures/` 디렉터리 경로를 반환하는 fixture를 하나 추가한다:

```python
@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"
```

### 4. `.gitignore` 확인

`phases/` 디렉터리가 `.gitignore`에 포함되어 있지 않은지 확인한다. `phases/`는 Git에 포함되어야 한다.

## Acceptance Criteria

```bash
pip install -r requirements.txt
python -m pytest --collect-only
python -c "import src; import tests"
```

- `pip install` 에러 없이 완료
- `pytest --collect-only` 에러 없이 실행 (수집 대상 0개는 정상)
- `import src`와 `import tests`가 에러 없이 동작

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md §2 디렉터리 구조에 맞는 파일만 생성했는가?
   - 불필요한 파일(setup.py, pyproject.toml, Makefile 등)을 추가하지 않았는가?
   - `src/__init__.py`와 `tests/__init__.py`가 빈 파일인가?
3. 결과에 따라 `phases/0-mvp/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `setup.py`, `pyproject.toml`, `Makefile`, `Dockerfile`을 생성하지 마라. 이유: MVP는 `pip install -r requirements.txt`만 사용한다.
- `requirements.txt`에 버전을 고정하지 마라. 이유: 로컬 도구이며 재현성은 README 절차로 보장한다.
- `src/` 안에 모듈 파일(rtzr_client.py 등)을 생성하지 마라. 이유: 각 모듈은 이후 step에서 생성한다.
- 기존 테스트를 깨뜨리지 마라.
