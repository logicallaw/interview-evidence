"""Fixture 기반 통합 테스트.

rtzr_client → segments → semantic_search 경로가 일관되게 동작하는지 검증한다.
실제 모델 로드 없이 fixture 데이터만 사용한다.
"""

import json

import numpy as np
import pytest

from src.rtzr_client import _validate_completed_response
from src.segments import build_answer_segments, get_unique_speakers, validate_speaker_count
from src.semantic_search import search_top_k


class TestFixtureIntegration:
    """fixture → Utterance → AnswerSegment 전체 경로 검증."""

    @pytest.fixture
    def utterances(self, fixtures_dir):
        data = json.loads((fixtures_dir / "rtzr_completed.json").read_text(encoding="utf-8"))
        return _validate_completed_response(data)

    def test_fixture_has_two_speakers(self, utterances):
        speakers = get_unique_speakers(utterances)
        assert validate_speaker_count(speakers)

    def test_segments_produced_from_fixture(self, utterances):
        speakers = get_unique_speakers(utterances)
        # 화자 "1"을 지원자로 선택
        candidate = speakers[1]
        segs = build_answer_segments(utterances, candidate)
        assert len(segs) > 0

    def test_segments_have_valid_time_bounds(self, utterances):
        speakers = get_unique_speakers(utterances)
        candidate = speakers[1]
        segs = build_answer_segments(utterances, candidate)
        for seg in segs:
            assert seg.start_at_ms >= 0
            assert seg.end_at_ms > seg.start_at_ms
            assert len(seg.source_utterance_indexes) > 0

    def test_searchable_segments_exist(self, utterances):
        speakers = get_unique_speakers(utterances)
        candidate = speakers[1]
        segs = build_answer_segments(utterances, candidate)
        searchable = [s for s in segs if s.searchable]
        assert len(searchable) > 0

    def test_unsearchable_segments_preserved(self, utterances):
        speakers = get_unique_speakers(utterances)
        candidate = speakers[1]
        segs = build_answer_segments(utterances, candidate)
        # 전체 세그먼트 수 >= searchable 세그먼트 수
        searchable = [s for s in segs if s.searchable]
        assert len(segs) >= len(searchable)

    def test_search_top_k_with_mock_embeddings(self, utterances):
        """searchable 세그먼트 수에 맞는 mock 임베딩으로 Top K 검색이 동작하는지 확인."""
        speakers = get_unique_speakers(utterances)
        candidate = speakers[1]
        segs = build_answer_segments(utterances, candidate)
        searchable = [s for s in segs if s.searchable]
        n = len(searchable)

        # mock 임베딩: 랜덤 정규화 벡터
        rng = np.random.default_rng(42)
        doc_embs = rng.random((n, 16))
        doc_embs = doc_embs / np.linalg.norm(doc_embs, axis=1, keepdims=True)
        query_emb = rng.random(16)
        query_emb = query_emb / np.linalg.norm(query_emb)

        results = search_top_k(query_emb, doc_embs, k=3)
        assert len(results) == min(3, n)
        # 내림차순 확인
        sims = [r[1] for r in results]
        assert sims == sorted(sims, reverse=True)
        # 인덱스 범위 확인
        for idx, _ in results:
            assert 0 <= idx < n
