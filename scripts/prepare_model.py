"""EmbeddingGemma 300M 모델을 다운로드하고 검증한다.

사용법: python scripts/prepare_model.py
"""

from __future__ import annotations

import sys

import numpy as np
from dotenv import load_dotenv

load_dotenv()

import os


def main() -> None:
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("오류: .env에 HF_TOKEN이 설정되어 있지 않습니다.")
        sys.exit(1)

    from sentence_transformers import SentenceTransformer

    model_name = "google/embeddinggemma-300m"

    print(f"모델 다운로드 중: {model_name}")
    # 다운로드 허용
    model = SentenceTransformer(model_name, local_files_only=False)
    print(f"장치: {model.device}")

    # 짧은 임베딩 검증
    query_emb = model.encode(
        "테스트 질의", prompt_name="Retrieval-query", normalize_embeddings=True
    )
    doc_emb = model.encode(
        "테스트 문서", prompt_name="Retrieval-document", normalize_embeddings=True
    )

    print(f"질의 임베딩 shape: {query_emb.shape}, norm: {np.linalg.norm(query_emb):.4f}")
    print(f"문서 임베딩 shape: {doc_emb.shape}, norm: {np.linalg.norm(doc_emb):.4f}")

    print("모델 준비 완료")


if __name__ == "__main__":
    main()
