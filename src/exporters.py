"""제한된 내보내기 모듈.

현재 질의와 검색 결과만 허용 필드로 구성해 UTF-8 JSON bytes로 직렬화한다.
"""

from __future__ import annotations

import json
from datetime import datetime

_RESULT_FIELDS = frozenset(
    ["rank", "similarity", "text", "start_at_ms", "end_at_ms", "source_utterance_indexes"]
)


def build_export_payload(
    audio_filename: str,
    query: str,
    candidate_speaker: str,
    results: list,
) -> dict:
    """현재 질의와 검색 결과로 export payload를 구성한다.

    허용 필드 외의 데이터는 인자로 받지도 않고 payload에 포함하지도 않는다.
    """
    filtered_results = []
    for r in results:
        filtered_results.append({k: r[k] for k in _RESULT_FIELDS if k in r})

    return {
        "audio_filename": audio_filename,
        "query": query,
        "created_at": datetime.now().isoformat(),
        "candidate_speaker": candidate_speaker,
        "results": filtered_results,
    }


def serialize_export(payload: dict) -> bytes:
    """payload를 UTF-8 JSON 바이트로 직렬화한다."""
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
