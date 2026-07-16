"""src/segments 단위 테스트."""

import json

import pytest

from src.rtzr_client import Utterance, _validate_completed_response
from src.segments import (
    AnswerSegment,
    build_answer_segments,
    compute_playback_bounds,
    get_unique_speakers,
    pick_representative_utterances,
    validate_speaker_count,
)


def _utt(index, speaker, start, duration, text):
    return Utterance(
        index=index, speaker=speaker, start_at_ms=start, duration_ms=duration, text=text
    )


# --- get_unique_speakers ---


class TestGetUniqueSpeakers:
    def test_two_speakers_order_preserved(self):
        utts = [_utt(0, "0", 0, 1000, "a"), _utt(1, "1", 1000, 1000, "b"), _utt(2, "0", 2000, 1000, "c")]
        assert get_unique_speakers(utts) == ["0", "1"]

    def test_single_speaker(self):
        assert get_unique_speakers([_utt(0, "0", 0, 1000, "a")]) == ["0"]

    def test_three_speakers(self):
        utts = [_utt(0, "0", 0, 1000, "a"), _utt(1, "1", 1000, 1000, "b"), _utt(2, "2", 2000, 1000, "c")]
        assert get_unique_speakers(utts) == ["0", "1", "2"]


# --- validate_speaker_count ---


class TestValidateSpeakerCount:
    def test_two(self):
        assert validate_speaker_count(["0", "1"]) is True

    def test_one(self):
        assert validate_speaker_count(["0"]) is False

    def test_three(self):
        assert validate_speaker_count(["0", "1", "2"]) is False


# --- pick_representative_utterances ---


class TestPickRepresentativeUtterances:
    def test_skips_short(self):
        utts = [
            _utt(0, "0", 0, 1000, "네"),
            _utt(1, "0", 1000, 5000, "안녕하세요 반갑습니다"),
            _utt(2, "0", 6000, 5000, "이것은 긴 발화입니다"),
        ]
        result = pick_representative_utterances(utts, "0", count=3)
        assert len(result) == 2
        assert result[0].index == 1

    def test_max_count(self):
        utts = [_utt(i, "0", i * 1000, 1000, f"충분히 긴 발화 텍스트 {i}") for i in range(10)]
        result = pick_representative_utterances(utts, "0", count=3)
        assert len(result) == 3

    def test_filters_by_speaker(self):
        utts = [
            _utt(0, "0", 0, 1000, "면접관의 긴 발화입니다"),
            _utt(1, "1", 1000, 1000, "지원자의 긴 발화입니다"),
        ]
        result = pick_representative_utterances(utts, "1", count=3)
        assert len(result) == 1
        assert result[0].speaker == "1"


# --- build_answer_segments ---


class TestBuildAnswerSegments:
    def test_consecutive_merged(self):
        utts = [
            _utt(0, "1", 0, 5000, "첫 번째 발화입니다"),
            _utt(1, "1", 5000, 5000, "두 번째 발화입니다"),
            _utt(2, "1", 10000, 5000, "세 번째 발화입니다"),
        ]
        segments = build_answer_segments(utts, "1")
        assert len(segments) == 1
        assert segments[0].text == "첫 번째 발화입니다 두 번째 발화입니다 세 번째 발화입니다"

    def test_other_speaker_splits(self):
        utts = [
            _utt(0, "1", 0, 5000, "지원자의 첫 답변입니다"),
            _utt(1, "1", 5000, 5000, "계속 답변하고 있습니다"),
            _utt(2, "0", 10000, 2000, "알겠습니다"),
            _utt(3, "1", 12000, 5000, "지원자의 두번째 답변입니다"),
        ]
        segments = build_answer_segments(utts, "1")
        assert len(segments) == 2

    def test_backchannel_splits(self):
        utts = [
            _utt(0, "1", 0, 5000, "지원자가 말하고 있습니다"),
            _utt(1, "0", 5000, 1000, "네"),
            _utt(2, "1", 6000, 5000, "이어서 답변합니다 계속"),
        ]
        segments = build_answer_segments(utts, "1")
        assert len(segments) == 2

    def test_end_at_ms(self):
        utts = [
            _utt(0, "1", 1000, 3000, "첫 번째 발화입니다"),
            _utt(1, "1", 4000, 2000, "두 번째 발화입니다"),
        ]
        segments = build_answer_segments(utts, "1")
        assert segments[0].end_at_ms == 6000

    def test_searchable_false_short(self):
        # "네맞아요" = 4자 (< 10)
        utts = [_utt(0, "1", 0, 1000, "네, 맞아요.")]
        segments = build_answer_segments(utts, "1")
        assert len(segments) == 1
        assert segments[0].searchable is False

    def test_searchable_true_10_chars(self):
        # "이것은열글자이상의텍스트" = 12자 (>= 10)
        utts = [_utt(0, "1", 0, 1000, "이것은 열 글자 이상의 텍스트")]
        segments = build_answer_segments(utts, "1")
        assert segments[0].searchable is True

    def test_searchable_boundary_9_chars(self):
        # 정확히 9자 → searchable=False
        utts = [_utt(0, "1", 0, 1000, "아홉글자의텍스트야")]  # 9자
        segments = build_answer_segments(utts, "1")
        assert segments[0].searchable is False

    def test_searchable_boundary_10_chars(self):
        # 정확히 10자 → searchable=True
        utts = [_utt(0, "1", 0, 1000, "열글자되는텍스트입니")]  # 10자
        segments = build_answer_segments(utts, "1")
        assert segments[0].searchable is True

    def test_unsearchable_still_in_list(self):
        utts = [
            _utt(0, "1", 0, 1000, "네."),
            _utt(1, "0", 1000, 1000, "질문입니다 이건 충분히 긴 질문"),
            _utt(2, "1", 2000, 5000, "이것은 충분히 긴 답변입니다 검색 가능합니다"),
        ]
        segments = build_answer_segments(utts, "1")
        assert len(segments) == 2
        assert segments[0].searchable is False
        assert segments[1].searchable is True

    def test_text_preserves_original(self):
        utts = [_utt(0, "1", 0, 1000, "안녕하세요, 반갑습니다!")]
        segments = build_answer_segments(utts, "1")
        assert segments[0].text == "안녕하세요, 반갑습니다!"

    def test_empty_utterances(self):
        assert build_answer_segments([], "1") == []

    def test_source_utterance_indexes(self):
        utts = [
            _utt(5, "1", 0, 3000, "첫 번째 긴 발화입니다"),
            _utt(6, "1", 3000, 3000, "두 번째 긴 발화입니다"),
        ]
        segments = build_answer_segments(utts, "1")
        assert segments[0].source_utterance_indexes == [5, 6]

    def test_does_not_mutate_input(self):
        utts = [
            _utt(0, "1", 5000, 3000, "나중 발화입니다 충분히 길게"),
            _utt(1, "1", 0, 3000, "먼저 발화입니다 충분히 길게"),
        ]
        original_order = [u.start_at_ms for u in utts]
        build_answer_segments(utts, "1")
        assert [u.start_at_ms for u in utts] == original_order


# --- compute_playback_bounds ---


class TestComputePlaybackBounds:
    def test_normal_range(self):
        start, end = compute_playback_bounds(52000, 92000, 550.0)
        assert start == 49
        assert end == 95

    def test_clamp_to_zero(self):
        start, _ = compute_playback_bounds(1000, 5000, 550.0)
        assert start == 0

    def test_clamp_to_audio_end(self):
        _, end = compute_playback_bounds(540000, 549000, 550.0)
        assert end == 550

    def test_returns_ints(self):
        start, end = compute_playback_bounds(52000, 92000, 550.0)
        assert isinstance(start, int)
        assert isinstance(end, int)


# --- fixture 기반 ---


class TestFixtureSegments:
    def test_fixture_produces_segments(self, fixtures_dir):
        data = json.loads((fixtures_dir / "rtzr_completed.json").read_text(encoding="utf-8"))
        utterances = _validate_completed_response(data)
        segments = build_answer_segments(utterances, "1")
        assert len(segments) > 0
        assert all(isinstance(s, AnswerSegment) for s in segments)
        assert any(s.searchable for s in segments)
