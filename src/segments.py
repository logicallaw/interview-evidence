"""답변 구간 구성과 화자 유틸리티.

Streamlit, HTTP, 모델 라이브러리에 의존하지 않는 순수 도메인 로직이다.
"""

from __future__ import annotations

import math
import re
import string
from dataclasses import dataclass, field

from src.rtzr_client import Utterance

_STRIP_RE = re.compile(r"[\s" + re.escape(string.punctuation) + "]")


def _stripped_len(text: str) -> int:
    """공백과 문장부호를 제거한 텍스트의 길이를 반환한다."""
    return len(_STRIP_RE.sub("", text))


@dataclass
class AnswerSegment:
    """연속 발화로 구성된 답변 구간."""

    text: str
    start_at_ms: int
    end_at_ms: int
    source_utterance_indexes: list[int] = field(default_factory=list)
    searchable: bool = True


def get_unique_speakers(utterances: list[Utterance]) -> list[str]:
    """발화에서 고유 화자 목록을 추출한다. 등장 순서를 유지한다."""
    seen: set[str] = set()
    result: list[str] = []
    for u in utterances:
        if u.speaker not in seen:
            seen.add(u.speaker)
            result.append(u.speaker)
    return result


def validate_speaker_count(speakers: list[str]) -> bool:
    """고유 화자가 정확히 2명인지 검증한다."""
    return len(speakers) == 2


def pick_representative_utterances(
    utterances: list[Utterance], speaker: str, count: int = 3
) -> list[Utterance]:
    """특정 화자의 대표 발화를 선택한다.

    시간순으로 앞에서부터 공백·문장부호 제거 후 5자 이상인 발화를 최대 count개 반환한다.
    역할을 자동 추론하지 않는다.
    """
    speaker_utts = sorted(
        (u for u in utterances if u.speaker == speaker),
        key=lambda u: u.start_at_ms,
    )
    result: list[Utterance] = []
    for u in speaker_utts:
        if _stripped_len(u.text) < 5:
            continue
        result.append(u)
        if len(result) >= count:
            break
    return result


def build_answer_segments(
    utterances: list[Utterance], candidate_speaker: str
) -> list[AnswerSegment]:
    """지원자의 연속 발화를 답변 구간으로 구성한다.

    원본 utterances 리스트를 변경하지 않는다.
    """
    sorted_utts = sorted(utterances, key=lambda u: u.start_at_ms)

    segments: list[AnswerSegment] = []
    buf_texts: list[str] = []
    buf_indexes: list[int] = []
    buf_start = 0
    buf_end = 0

    def _flush() -> None:
        if not buf_texts:
            return
        text = " ".join(buf_texts)
        segments.append(
            AnswerSegment(
                text=text,
                start_at_ms=buf_start,
                end_at_ms=buf_end,
                source_utterance_indexes=list(buf_indexes),
                searchable=_stripped_len(text) >= 10,
            )
        )

    for u in sorted_utts:
        if u.speaker == candidate_speaker:
            if not buf_texts:
                buf_start = u.start_at_ms
            buf_texts.append(u.text)
            buf_indexes.append(u.index)
            buf_end = u.start_at_ms + u.duration_ms
        else:
            _flush()
            buf_texts.clear()
            buf_indexes.clear()

    _flush()
    return segments


def compute_playback_bounds(
    start_at_ms: int, end_at_ms: int, audio_duration_sec: float
) -> tuple[int, int]:
    """오디오 재생 경계를 계산한다.

    답변 시작 시점부터 종료 3초 후까지, 음원 경계 안에서 재생한다.
    반환: (start_sec, end_sec) — 둘 다 정수.
    """
    start_sec = max(0, math.floor(start_at_ms / 1000))
    end_sec = min(math.floor(audio_duration_sec), math.ceil(end_at_ms / 1000) + 3)
    return start_sec, end_sec
