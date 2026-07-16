"""RTZR 일반 STT API 어댑터.

인증, 전사 요청, 상태 조회, 완료 응답 검증을 담당한다.
폴링 루프는 이 모듈에 포함하지 않는다.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://openapi.vito.ai/v1"

_TRANSCRIPTION_CONFIG = {
    "model_name": "sommers",
    "domain": "GENERAL",
    "use_diarization": True,
    "diarization": {"spk_count": 2},
    "use_word_timestamp": False,
    "use_itn": True,
    "use_disfluency_filter": True,
    "use_paragraph_splitter": True,
    "paragraph_splitter": {"max": 130},
}

_RETRY_DELAYS = [2, 4, 8]
_TIMEOUT = (10, 30)  # (connect_timeout, read_timeout)
_UPLOAD_TIMEOUT = (10, 120)  # 업로드는 파일 크기에 따라 read timeout을 넓게


class TranscriptionError(Exception):
    """전사 관련 기본 예외."""


class RetryableError(TranscriptionError):
    """재시도 가능한 일시적 오류 (네트워크, 429, 5xx)."""


class FatalError(TranscriptionError):
    """즉시 중단해야 하는 오류 (인증, 검증, 4xx)."""


@dataclass
class Utterance:
    """정규화된 발화."""

    index: int
    speaker: str
    start_at_ms: int
    duration_ms: int
    text: str


@dataclass
class TranscriptionJob:
    """정규화된 전사 작업 상태."""

    id: str
    status: str  # "transcribing" | "completed" | "failed"
    utterances: list[Utterance] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


def authenticate(client_id: str, client_secret: str) -> str:
    """RTZR OAuth 토큰을 획득한다. 실패 시 예외를 발생시킨다."""
    logger.info("RTZR 인증 요청 시작")
    resp = requests.post(
        f"{_BASE_URL}/authenticate",
        data={"client_id": client_id, "client_secret": client_secret},
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        logger.error("RTZR 인증 실패 (HTTP %d)", resp.status_code)
        raise RuntimeError(f"RTZR 인증 실패 (HTTP {resp.status_code})")
    logger.info("RTZR 인증 성공")
    return resp.json()["access_token"]


def create_transcription(token: str, file_bytes: bytes, filename: str) -> str:
    """전사 요청을 생성하고 transcribe_id를 반환한다.

    429 A0002 에러만 2초, 4초, 8초 간격으로 최대 3회 재시도한다.
    네트워크 타임아웃과 그 외 오류는 재시도하지 않는다.
    """
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, file_bytes)}
    data = {"config": json.dumps(_TRANSCRIPTION_CONFIG)}

    logger.info("RTZR 전사 요청 시작 (파일: %s)", filename)

    resp = None
    for attempt in range(4):  # 1 initial + 3 retries
        resp = requests.post(
            f"{_BASE_URL}/transcribe",
            headers=headers,
            files=files,
            data=data,
            timeout=_UPLOAD_TIMEOUT,
        )
        if resp.status_code == 429:
            body = resp.json()
            if body.get("code") == "A0002" and attempt < 3:
                logger.warning(
                    "RTZR 429 A0002 — %d초 후 재시도 (%d/3)",
                    _RETRY_DELAYS[attempt],
                    attempt + 1,
                )
                time.sleep(_RETRY_DELAYS[attempt])
                continue
        break

    logger.info("RTZR 전사 요청 응답 (HTTP %d)", resp.status_code)
    if resp.status_code != 200:
        logger.error("RTZR 전사 요청 실패 (HTTP %d)", resp.status_code)
        raise RuntimeError(f"RTZR 전사 요청 실패 (HTTP {resp.status_code})")
    transcribe_id = resp.json()["id"]
    logger.info("RTZR 전사 접수 완료 (transcribe_id: %s)", transcribe_id)
    return transcribe_id


def get_transcription(token: str, transcribe_id: str) -> TranscriptionJob:
    """전사 상태를 조회하고 정규화된 TranscriptionJob을 반환한다.

    일시적 오류(네트워크, 429, 5xx)는 RetryableError,
    복구 불가 오류(인증, 4xx, 검증)는 FatalError를 발생시킨다.
    """
    try:
        logger.debug("RTZR 전사 조회 (transcribe_id: %s)", transcribe_id)
        resp = requests.get(
            f"{_BASE_URL}/transcribe/{transcribe_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            if resp.status_code in (429, 500, 502, 503, 504):
                raise RetryableError(
                    f"RTZR 전사 조회 일시적 오류 (HTTP {resp.status_code})"
                )
            raise FatalError(
                f"RTZR 전사 조회 실패 (HTTP {resp.status_code})"
            )

        data = resp.json()
        status = data.get("status", "")

        if status == "completed":
            utterances = _validate_completed_response(data)
            logger.info(
                "RTZR 전사 완료 (transcribe_id: %s, 발화 %d개)",
                transcribe_id,
                len(utterances),
            )
            return TranscriptionJob(
                id=transcribe_id,
                status="completed",
                utterances=utterances,
            )

        if status == "failed":
            logger.error(
                "RTZR 전사 실패 (transcribe_id: %s, code: %s)",
                transcribe_id,
                data.get("code"),
            )
            return TranscriptionJob(
                id=transcribe_id,
                status="failed",
                error_code=data.get("code"),
                error_message=data.get("message"),
            )

        logger.debug("RTZR 전사 진행 중 (transcribe_id: %s, status: %s)", transcribe_id, status)
        return TranscriptionJob(id=transcribe_id, status="transcribing")
    except (RetryableError, FatalError):
        raise
    except (requests.ConnectionError, requests.Timeout) as e:
        raise RetryableError(f"RTZR 전사 조회 네트워크 오류: {e}") from e
    except Exception as e:
        raise FatalError(f"RTZR 전사 조회 처리 오류: {e}") from e


def _validate_completed_response(data: dict) -> list[Utterance]:
    """완료 응답의 utterances를 검증하고 Utterance 리스트로 변환한다."""
    results = data.get("results")
    if results is None:
        raise ValueError("완료 응답에 results가 없습니다")

    raw_utterances = results.get("utterances")
    if raw_utterances is None:
        raise ValueError("완료 응답에 utterances가 없습니다")

    utterances: list[Utterance] = []
    for i, u in enumerate(raw_utterances):
        for key in ("spk", "start_at", "duration", "msg"):
            if key not in u:
                raise ValueError(f"발화 {i}에 필수 필드 '{key}'가 없습니다")
        utterances.append(
            Utterance(
                index=i,
                speaker=str(u["spk"]),
                start_at_ms=int(u["start_at"]),
                duration_ms=int(u["duration"]),
                text=str(u["msg"]),
            )
        )

    return utterances
