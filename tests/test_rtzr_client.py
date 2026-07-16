"""src/rtzr_client 단위 테스트."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.rtzr_client import (
    Utterance,
    _validate_completed_response,
    authenticate,
    create_transcription,
    get_transcription,
)


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


@pytest.fixture
def completed_fixture(fixtures_dir):
    path = fixtures_dir / "rtzr_completed.json"
    return json.loads(path.read_text(encoding="utf-8"))


# --- _validate_completed_response ---


class TestValidateCompletedResponse:
    def test_valid_fixture(self, completed_fixture):
        utterances = _validate_completed_response(completed_fixture)
        assert len(utterances) > 0
        assert all(isinstance(u, Utterance) for u in utterances)

    def test_missing_spk(self):
        data = {"results": {"utterances": [{"start_at": 0, "duration": 1000, "msg": "t"}]}}
        with pytest.raises(ValueError, match="spk"):
            _validate_completed_response(data)

    def test_missing_start_at(self):
        data = {"results": {"utterances": [{"spk": 0, "duration": 1000, "msg": "t"}]}}
        with pytest.raises(ValueError, match="start_at"):
            _validate_completed_response(data)

    def test_missing_duration(self):
        data = {"results": {"utterances": [{"spk": 0, "start_at": 0, "msg": "t"}]}}
        with pytest.raises(ValueError, match="duration"):
            _validate_completed_response(data)

    def test_missing_msg(self):
        data = {"results": {"utterances": [{"spk": 0, "start_at": 0, "duration": 1000}]}}
        with pytest.raises(ValueError, match="msg"):
            _validate_completed_response(data)

    def test_empty_utterances(self):
        data = {"results": {"utterances": []}}
        utterances = _validate_completed_response(data)
        assert utterances == []


# --- authenticate ---


class TestAuthenticate:
    @patch("src.rtzr_client.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = _mock_response(200, {"access_token": "tok123"})
        assert authenticate("id", "secret") == "tok123"

    @patch("src.rtzr_client.requests.post")
    def test_failure_401(self, mock_post):
        mock_post.return_value = _mock_response(401, {})
        with pytest.raises(RuntimeError, match="인증 실패"):
            authenticate("id", "secret")


# --- create_transcription ---


class TestCreateTranscription:
    @patch("src.rtzr_client.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = _mock_response(200, {"id": "tx-001"})
        assert create_transcription("tok", b"audio", "test.wav") == "tx-001"

    @patch("src.rtzr_client.time.sleep")
    @patch("src.rtzr_client.requests.post")
    def test_retry_429_a0002_then_success(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _mock_response(429, {"code": "A0002"}),
            _mock_response(429, {"code": "A0002"}),
            _mock_response(200, {"id": "tx-002"}),
        ]
        assert create_transcription("tok", b"audio", "test.wav") == "tx-002"
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)

    @patch("src.rtzr_client.time.sleep")
    @patch("src.rtzr_client.requests.post")
    def test_retry_429_a0002_exhausted(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _mock_response(429, {"code": "A0002"}),
            _mock_response(429, {"code": "A0002"}),
            _mock_response(429, {"code": "A0002"}),
            _mock_response(429, {"code": "A0002"}),
        ]
        with pytest.raises(RuntimeError):
            create_transcription("tok", b"audio", "test.wav")
        assert mock_sleep.call_count == 3


# --- get_transcription ---


class TestGetTranscription:
    @patch("src.rtzr_client.requests.get")
    def test_completed(self, mock_get):
        mock_get.return_value = _mock_response(200, {
            "status": "completed",
            "results": {
                "utterances": [
                    {"spk": 0, "start_at": 0, "duration": 5000, "msg": "안녕하세요"},
                ],
            },
        })
        job = get_transcription("tok", "tx-001")
        assert job.status == "completed"
        assert len(job.utterances) == 1
        assert job.utterances[0].text == "안녕하세요"
        assert job.utterances[0].speaker == "0"
        assert job.utterances[0].start_at_ms == 0
        assert job.utterances[0].duration_ms == 5000


# --- fixture 파싱 ---


class TestFixtureParsing:
    def test_fixture_passes_validation(self, completed_fixture):
        utterances = _validate_completed_response(completed_fixture)
        assert len(utterances) > 0
        speakers = {u.speaker for u in utterances}
        assert speakers == {"0", "1"}

    def test_fixture_indexes_are_sequential(self, completed_fixture):
        utterances = _validate_completed_response(completed_fixture)
        for i, u in enumerate(utterances):
            assert u.index == i

    def test_fixture_has_no_identifying_metadata(self, completed_fixture):
        assert "owner" not in completed_fixture
        assert "created_at" not in completed_fixture
        assert "access_token" not in completed_fixture
