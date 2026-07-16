"""src/exporters 단위 테스트."""

import json
from datetime import datetime

import pytest

from src.exporters import build_export_payload, serialize_export


def _sample_results():
    return [
        {
            "rank": 1,
            "similarity": 0.8234567890123456,
            "text": "지원자의 첫 번째 답변입니다",
            "start_at_ms": 52000,
            "end_at_ms": 92000,
            "source_utterance_indexes": [3, 4, 5],
        },
        {
            "rank": 2,
            "similarity": 0.7123456789012345,
            "text": "두 번째 답변 구간",
            "start_at_ms": 120000,
            "end_at_ms": 150000,
            "source_utterance_indexes": [10],
        },
    ]


class TestBuildExportPayload:
    def test_allowed_top_level_fields_only(self):
        payload = build_export_payload("test.wav", "질의", "1", _sample_results())
        assert set(payload.keys()) == {
            "audio_filename", "query", "created_at", "candidate_speaker", "results"
        }

    def test_result_fields_only(self):
        payload = build_export_payload("test.wav", "질의", "1", _sample_results())
        expected = {"rank", "similarity", "text", "start_at_ms", "end_at_ms", "source_utterance_indexes"}
        for r in payload["results"]:
            assert set(r.keys()) == expected

    def test_extra_fields_ignored(self):
        results = [
            {
                "rank": 1,
                "similarity": 0.9,
                "text": "답변",
                "start_at_ms": 0,
                "end_at_ms": 1000,
                "source_utterance_indexes": [0],
                "extra_field": "should be ignored",
                "secret": "token123",
            }
        ]
        payload = build_export_payload("test.wav", "질의", "1", results)
        assert "extra_field" not in payload["results"][0]
        assert "secret" not in payload["results"][0]

    def test_created_at_iso8601(self):
        payload = build_export_payload("test.wav", "질의", "1", [])
        # ISO 8601 파싱 가능 여부 확인
        parsed = datetime.fromisoformat(payload["created_at"])
        assert isinstance(parsed, datetime)

    def test_empty_results(self):
        payload = build_export_payload("test.wav", "질의", "1", [])
        assert payload["results"] == []
        assert payload["audio_filename"] == "test.wav"
        assert payload["query"] == "질의"

    def test_similarity_precision(self):
        value = 0.8234567890123456
        results = [
            {
                "rank": 1,
                "similarity": value,
                "text": "답변",
                "start_at_ms": 0,
                "end_at_ms": 1000,
                "source_utterance_indexes": [0],
            }
        ]
        payload = build_export_payload("test.wav", "질의", "1", results)
        assert payload["results"][0]["similarity"] == value


class TestSerializeExport:
    def test_returns_bytes(self):
        payload = build_export_payload("test.wav", "질의", "1", [])
        result = serialize_export(payload)
        assert isinstance(result, bytes)

    def test_korean_preserved(self):
        payload = build_export_payload("test.wav", "한글 질의", "1", _sample_results())
        result = serialize_export(payload)
        text = result.decode("utf-8")
        assert "한글 질의" in text
        assert "지원자의 첫 번째 답변입니다" in text

    def test_roundtrip(self):
        payload = build_export_payload("test.wav", "질의", "1", _sample_results())
        result = serialize_export(payload)
        parsed = json.loads(result)
        assert parsed["audio_filename"] == "test.wav"
        assert parsed["query"] == "질의"
        assert len(parsed["results"]) == 2
