"""src/semantic_search 단위 테스트.

실제 모델 로드 없이 모킹으로 테스트한다.
"""

from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from src.semantic_search import (
    embed_documents,
    embed_query,
    load_model,
    search_top_k,
)


# --- search_top_k ---


class TestSearchTopK:
    def test_descending_order(self):
        query = np.array([1.0, 0.0, 0.0])
        docs = np.array([
            [0.5, 0.5, 0.0],   # cos ≈ 0.707
            [1.0, 0.0, 0.0],   # cos = 1.0
            [0.0, 1.0, 0.0],   # cos = 0.0
        ])
        # 정규화
        docs = docs / np.linalg.norm(docs, axis=1, keepdims=True)
        query = query / np.linalg.norm(query)

        results = search_top_k(query, docs, k=3)

        assert len(results) == 3
        assert results[0][0] == 1  # cos=1.0이 가장 높음
        assert results[1][0] == 0  # cos≈0.707
        assert results[2][0] == 2  # cos=0.0
        # 내림차순 확인
        sims = [r[1] for r in results]
        assert sims == sorted(sims, reverse=True)

    def test_k3_with_5_docs(self):
        query = np.array([1.0, 0.0])
        docs = np.array([
            [1.0, 0.0],
            [0.9, 0.1],
            [0.8, 0.2],
            [0.7, 0.3],
            [0.6, 0.4],
        ])
        docs = docs / np.linalg.norm(docs, axis=1, keepdims=True)
        query = query / np.linalg.norm(query)

        results = search_top_k(query, docs, k=3)
        assert len(results) == 3

    def test_k3_with_2_docs(self):
        query = np.array([1.0, 0.0])
        docs = np.array([
            [1.0, 0.0],
            [0.0, 1.0],
        ])
        results = search_top_k(query, docs, k=3)
        assert len(results) == 2

    def test_empty_docs(self):
        query = np.array([1.0, 0.0])
        docs = np.array([]).reshape(0, 2)
        results = search_top_k(query, docs, k=3)
        assert results == []

    def test_single_doc(self):
        query = np.array([1.0, 0.0])
        docs = np.array([[0.5, 0.5]])
        docs = docs / np.linalg.norm(docs, axis=1, keepdims=True)
        query = query / np.linalg.norm(query)

        results = search_top_k(query, docs, k=3)
        assert len(results) == 1
        assert results[0][0] == 0


# --- embed_documents ---


class TestEmbedDocuments:
    def test_encode_called_with_correct_args(self):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.zeros((3, 256))

        texts = ["첫 번째", "두 번째", "세 번째"]
        embed_documents(mock_model, texts)

        mock_model.encode.assert_called_once_with(
            texts,
            prompt_name="Retrieval-document",
            normalize_embeddings=True,
            batch_size=8,
        )


# --- embed_query ---


class TestEmbedQuery:
    def test_encode_called_with_correct_args(self):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.zeros(256)

        embed_query(mock_model, "테스트 질의")

        mock_model.encode.assert_called_once_with(
            "테스트 질의",
            prompt_name="Retrieval-query",
            normalize_embeddings=True,
        )


# --- load_model MPS 폴백 ---


class TestLoadModelMpsFallback:
    @patch("src.semantic_search.SentenceTransformer")
    def test_mps_failure_falls_back_to_cpu(self, mock_st_cls):
        """MPS 로드 실패 시 CPU로 재시도하는지 확인한다."""
        mock_mps_model = MagicMock()
        mock_mps_model.encode.side_effect = RuntimeError("MPS error")
        mock_cpu_model = MagicMock()

        mock_st_cls.side_effect = [mock_mps_model, mock_cpu_model]

        with patch("src.semantic_search.torch") as mock_torch:
            mock_torch.backends.mps.is_available.return_value = True

            model = load_model(device=None, local_files_only=True)

        assert model is mock_cpu_model
        assert mock_st_cls.call_count == 2
        # 첫 호출: MPS
        mock_st_cls.assert_any_call(
            "google/embeddinggemma-300m", device="mps", local_files_only=True
        )
        # 두 번째 호출: CPU
        mock_st_cls.assert_any_call(
            "google/embeddinggemma-300m", device="cpu", local_files_only=True
        )

    @patch("src.semantic_search.SentenceTransformer")
    def test_explicit_device_skips_fallback(self, mock_st_cls):
        """device가 명시되면 폴백 없이 해당 장치를 사용한다."""
        mock_model = MagicMock()
        mock_st_cls.return_value = mock_model

        model = load_model(device="cpu", local_files_only=True)

        assert model is mock_model
        mock_st_cls.assert_called_once_with(
            "google/embeddinggemma-300m", device="cpu", local_files_only=True
        )

    @patch("src.semantic_search.SentenceTransformer")
    def test_both_fail_raises_runtime_error(self, mock_st_cls):
        """MPS와 CPU 모두 실패하면 RuntimeError를 발생시킨다."""
        mock_mps_model = MagicMock()
        mock_mps_model.encode.side_effect = RuntimeError("MPS error")
        mock_st_cls.side_effect = [mock_mps_model, RuntimeError("CPU error")]

        with patch("src.semantic_search.torch") as mock_torch:
            mock_torch.backends.mps.is_available.return_value = True

            with pytest.raises(RuntimeError, match="모델을 로드할 수 없습니다"):
                load_model(device=None, local_files_only=True)
