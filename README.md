# Interview Evidence

RTZR 일반 STT와 EmbeddingGemma를 이용해, 면접 평가 기준과 관련된 지원자 답변 구간을 찾아 원음으로 재확인하게 하는 근거 기반 인터뷰 리뷰어.

## 설치 및 실행

```bash
# 1. 가상환경 생성
python -m venv .venv && source .venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경 변수 설정 (.env.example 참고)
cp .env.example .env
# .env 파일에 RTZR_CLIENT_ID, RTZR_CLIENT_SECRET, HF_TOKEN 입력

# 4. 모델 사전 준비
python scripts/prepare_model.py

# 5. 단위 테스트
python -m pytest

# 6. 앱 실행
streamlit run app.py
```

## Sample Audio

The `interview-sample.wav` file in this repository was generated using NAVER CLOVA Dubbing from an original script written by [logicallaw](https://github.com/logicallaw).

An audible attribution notice for NAVER CLOVA Dubbing is included at the beginning of the audio file.
