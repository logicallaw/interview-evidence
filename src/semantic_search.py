"""로컬 의미 검색 모듈.

EmbeddingGemma 300M을 이용한 임베딩과 코사인 유사도 검색을 담당한다.
Streamlit, HTTP에 의존하지 않는다.
"""

from __future__ import annotations

import logging

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "google/embeddinggemma-300m"

logger = logging.getLogger(__name__)


def load_model(
    device: str | None = None, local_files_only: bool = True
) -> SentenceTransformer:
    """EmbeddingGemma 300M 모델을 로드한다.

    장치 선택:
    1. device가 명시되면 해당 장치를 사용한다.
    2. device가 None이면 MPS 사용 가능 여부를 확인한다.
    3. MPS 로드 또는 짧은 추론이 실패하면 CPU로 한 번만 대체한다.
    4. CPU에서도 실패하면 RuntimeError를 발생시킨다.
    """
    if device is not None:
        return SentenceTransformer(
            _MODEL_NAME, device=device, local_files_only=local_files_only
        )

    # MPS 사용 가능 여부 확인
    try:
        if torch.backends.mps.is_available():
            try:
                model = SentenceTransformer(
                    _MODEL_NAME, device="mps", local_files_only=local_files_only
                )
                # 짧은 추론으로 MPS 동작 검증
                model.encode("test", normalize_embeddings=True)
                return model
            except Exception:
                logger.warning("MPS 로드 실패, CPU로 대체합니다")
    except Exception:
        pass

    # CPU 대체
    try:
        return SentenceTransformer(
            _MODEL_NAME, device="cpu", local_files_only=local_files_only
        )
    except Exception as exc:
        raise RuntimeError(
            f"모델을 로드할 수 없습니다. "
            f"python scripts/prepare_model.py를 먼저 실행하세요."
        ) from exc


def embed_documents(model: SentenceTransformer, texts: list[str]) -> np.ndarray:
    """답변 텍스트를 임베딩한다.

    - prompt_name="Retrieval-document"
    - normalize_embeddings=True
    - batch_size=8
    - 반환: (N, D) ndarray
    """
    return model.encode(
        texts,
        prompt_name="Retrieval-document",
        normalize_embeddings=True,
        batch_size=8,
    )


def embed_query(model: SentenceTransformer, query: str) -> np.ndarray:
    """질의 텍스트를 임베딩한다.

    - prompt_name="Retrieval-query"
    - normalize_embeddings=True
    - 반환: (D,) ndarray
    """
    return model.encode(
        query,
        prompt_name="Retrieval-query",
        normalize_embeddings=True,
    )


def search_top_k(
    query_embedding: np.ndarray,
    doc_embeddings: np.ndarray,
    k: int = 3,
) -> list[tuple[int, float]]:
    """코사인 유사도 기반 Top K를 반환한다.

    - 이미 정규화된 벡터이므로 dot product = cosine similarity
    - 내림차순 정렬
    - 반환: [(index, similarity), ...], 길이 = min(k, len(doc_embeddings))
    - doc_embeddings가 비어있으면 빈 리스트 반환
    """
    if doc_embeddings.size == 0:
        return []

    q = query_embedding.reshape(1, -1)
    similarities = (q @ doc_embeddings.T).flatten()

    top_count = min(k, len(similarities))
    top_indices = np.argsort(similarities)[::-1][:top_count]

    return [(int(idx), float(similarities[idx])) for idx in top_indices]
