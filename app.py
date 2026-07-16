"""Interview Evidence — Streamlit 앱.

표현 계층과 세션 오케스트레이션만 담당한다.
도메인 로직은 src/ 모듈을 호출한다.
"""

from __future__ import annotations

import io
import logging
import os
import time
import warnings
import wave

# transformers 비전 모듈이 torchvision을 탐색할 때 나오는 경고 억제
warnings.filterwarnings("ignore", message=".*torchvision.*")

import streamlit as st
from dotenv import load_dotenv

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.DEBUG,
)
logging.getLogger("streamlit.watcher.local_sources_watcher").setLevel(logging.ERROR)

from src import exporters, rtzr_client, segments, semantic_search


# ── 헬퍼 ─────────────────────────────────────────────────


def _fmt(ms: int) -> str:
    """밀리초를 MM:SS 형식으로 변환한다."""
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def _wav_duration(data: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(data)) as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return None


def _prev_interviewer(utterances, source_indexes, candidate):
    """선택 답변의 직전 면접관 발화를 찾는다."""
    boundary = min(source_indexes)
    best = None
    for u in utterances:
        if u.index < boundary and u.speaker != candidate:
            if best is None or u.index > best.index:
                best = u
    return best


def _spk_label(speaker, speakers):
    idx = speakers.index(speaker) + 1 if speaker in speakers else 0
    return f"화자 {idx}"


def _spk_role(speaker, speakers, candidate):
    label = _spk_label(speaker, speakers)
    if candidate is None:
        return label
    return f"{label} · 지원자" if speaker == candidate else f"{label} · 면접관"


def _clear_post_transcription():
    for k in [
        "transcribe_id", "transcription_status", "utterances", "speakers",
        "candidate_speaker", "segments", "doc_embeddings",
        "query", "search_results", "selected_result_index", "rtzr_token",
    ]:
        st.session_state[k] = None


def _clear_post_speaker():
    for k in ["segments", "doc_embeddings", "query", "search_results", "selected_result_index"]:
        st.session_state[k] = None


# ── 모델 캐시 ────────────────────────────────────────────


@st.cache_resource
def _load_model():
    try:
        return semantic_search.load_model()
    except Exception:
        return None


# ── CSS / 사전 조건 / 세션 ────────────────────────────────


def _inject_css():
    st.markdown(
        "<style>"
        ".depth-bar{display:flex;gap:2rem;padding:.75rem 0;"
        "border-bottom:1px solid #E2E8F0;margin-bottom:1.5rem}"
        ".depth-bar span{font-size:15px;color:#64748B;padding-bottom:.5rem}"
        ".depth-bar span.on{color:#0284C7;font-weight:600;"
        "border-bottom:2px solid #0284C7}"
        ".note{color:#64748B;font-size:14px;font-style:italic}"
        "div[data-testid='stButton']>button[kind='primary']"
        "{background:#0284C7;border-color:#0284C7}"
        "div[data-testid='stButton']>button[kind='primary']:hover"
        "{background:#0369A1;border-color:#0369A1}"
        "</style>",
        unsafe_allow_html=True,
    )


def _check_credentials():
    if not os.environ.get("RTZR_CLIENT_ID") or not os.environ.get("RTZR_CLIENT_SECRET"):
        st.error(
            "RTZR 자격 증명이 설정되어 있지 않습니다. "
            "`.env` 파일에 `RTZR_CLIENT_ID`와 `RTZR_CLIENT_SECRET`을 설정하세요."
        )
        st.stop()


def _init_state():
    defaults = dict(
        current_depth="audio_setup",
        audio_file=None, audio_bytes=None, audio_filename=None, audio_duration_sec=None,
        transcribe_id=None, transcription_status=None,
        utterances=None, speakers=None,
        candidate_speaker=None, segments=None, doc_embeddings=None,
        query=None, search_results=None, selected_result_index=None,
        rtzr_token=None, device_info=None,
    )
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _render_depth_bar():
    cur = st.session_state.current_depth
    pairs = [("audio_setup", "음성 준비"), ("speaker_review", "화자 확인"), ("evidence_search", "근거 찾기")]
    spans = "".join(
        f'<span class="{"on" if k == cur else ""}">{n}</span>' for k, n in pairs
    )
    st.markdown(f'<div class="depth-bar">{spans}</div>', unsafe_allow_html=True)


# ── Depth 1: 음성 준비 ──────────────────────────────────


def _render_audio_setup():
    st.markdown("### Interview Evidence")
    st.markdown("면접에서 다시 확인할 답변을 찾아보세요.")
    st.markdown("음성 파일을 전사한 뒤, 평가 기준과 관련된 구간을 원음으로 확인할 수 있습니다.")
    st.caption("지원자를 자동 평가하거나 점수를 매기지 않습니다.")

    uploaded = st.file_uploader(
        "면접 음성 파일",
        type=["wav", "mp3", "m4a", "flac", "webm"],
        help="한 명의 면접관과 한 명의 지원자가 대화한 파일 1개를 선택하세요.",
    )
    if uploaded is not None and st.session_state.audio_filename != uploaded.name:
        _clear_post_transcription()
        st.session_state.audio_filename = uploaded.name
        st.session_state.audio_bytes = uploaded.getvalue()
        st.session_state.audio_duration_sec = _wav_duration(st.session_state.audio_bytes)

    if st.session_state.audio_bytes is None:
        return

    # 파일 정보
    dur = st.session_state.audio_duration_sec
    info = st.session_state.audio_filename
    if dur is not None:
        info += f" · {int(dur) // 60:02d}:{int(dur) % 60:02d}"
    st.markdown(f"**선택된 파일**: {info}")
    st.caption("선택한 파일은 전사를 위해 RTZR로 전송됩니다.")

    # 이미 전사 완료
    if st.session_state.utterances is not None:
        st.success("전사가 완료되었습니다.")
        if st.button("화자 확인으로 이동", type="primary"):
            st.session_state.current_depth = "speaker_review"
            st.rerun()
        return

    # 타임아웃 후 재개
    if st.session_state.transcription_status == "timeout":
        st.warning("폴링 시간 제한에 도달했습니다. 전사가 아직 진행 중일 수 있습니다.")
        if st.button("상태 조회 재개", type="primary"):
            with st.status("전사 결과를 기다리고 있습니다...", expanded=True) as status:
                _poll_loop(st.session_state.rtzr_token, st.session_state.transcribe_id, status)
        return

    if st.button("전사 시작", type="primary"):
        _start_transcription()


def _start_transcription():
    with st.status("전사 진행 중...", expanded=True) as status:
        # 인증
        status.update(label="인증 중...")
        try:
            token = rtzr_client.authenticate(
                os.environ["RTZR_CLIENT_ID"], os.environ["RTZR_CLIENT_SECRET"],
            )
            st.session_state.rtzr_token = token
        except Exception:
            st.error("인증에 실패했습니다. `.env`의 자격 증명을 확인하세요.")
            return

        # 전사 요청
        status.update(label="파일 전송 중...")
        try:
            tid = rtzr_client.create_transcription(
                token, st.session_state.audio_bytes, st.session_state.audio_filename,
            )
            st.session_state.transcribe_id = tid
            st.session_state.transcription_status = "transcribing"
        except Exception:
            st.error("전사 요청에 실패했습니다. 다시 시도하세요.")
            return

        # 폴링
        status.update(label="음성 파일을 전송했습니다. 현재 전사 결과를 기다리고 있습니다.")
        _poll_loop(token, tid, status)


def _poll_loop(token, tid, status):
    elapsed = 0
    backoff = 1
    while elapsed < 3600:
        try:
            job = rtzr_client.get_transcription(token, tid)
            backoff = 1
            if job.status == "completed":
                st.session_state.utterances = job.utterances
                st.session_state.transcription_status = "completed"
                st.session_state.speakers = segments.get_unique_speakers(job.utterances)
                status.update(label="전사 완료", state="complete")
                st.session_state.current_depth = "speaker_review"
                st.rerun()
                return
            if job.status == "failed":
                st.session_state.transcription_status = "failed"
                msg = job.error_message or "알 수 없는 오류"
                status.update(label="전사 실패", state="error")
                st.error(f"전사가 실패했습니다: {msg}\n\n새 파일을 업로드하거나 다시 시도하세요.")
                return
        except Exception:
            backoff = min(backoff * 2, 8)
        sleep_sec = 5 * backoff
        time.sleep(sleep_sec)
        elapsed += sleep_sec

    st.session_state.transcription_status = "timeout"
    status.update(label="시간 제한 도달", state="error")


# ── Depth 2: 화자 확인 ──────────────────────────────────


def _render_speaker_review():
    if st.button("← 음성 준비"):
        st.session_state.current_depth = "audio_setup"
        st.rerun()

    st.markdown("### 화자를 확인해 주세요")
    st.markdown("지원자에 해당하는 화자를 선택하면 해당 화자의 답변만 검색 대상으로 사용합니다.")

    utts = st.session_state.utterances
    spks = st.session_state.speakers

    if not segments.validate_speaker_count(spks):
        st.warning(
            "이 버전은 두 명이 대화한 인터뷰만 지원합니다.\n\n"
            "전사 내용은 확인할 수 있지만 관련 답변 검색은 사용할 수 없습니다."
        )
        _render_timeline(utts, spks, None)
        return

    for spk in spks:
        label = _spk_label(spk, spks)
        is_sel = st.session_state.candidate_speaker == spk
        with st.container(border=True):
            st.markdown(f"**{label}**")
            for rep in segments.pick_representative_utterances(utts, spk, count=3):
                st.markdown(f'> "{rep.text}"')
            btn_text = "✓ 지원자로 선택됨" if is_sel else "지원자로 선택"
            if st.button(btn_text, key=f"sel_{spk}", type="primary"):
                if st.session_state.candidate_speaker != spk:
                    _invalidate_and_index(utts, spk)
                    st.rerun()

    with st.expander("전체 전사 내용 확인"):
        _render_timeline(utts, spks, st.session_state.candidate_speaker)


def _invalidate_and_index(utts, spk):
    """화자 변경 → 무효화 → 세그먼트·임베딩 재생성 → Depth 3."""
    _clear_post_speaker()
    st.session_state.candidate_speaker = spk
    segs = segments.build_answer_segments(utts, spk)
    st.session_state.segments = segs

    model = _load_model()
    if model is not None:
        searchable = [s.text for s in segs if s.searchable]
        if searchable:
            st.session_state.doc_embeddings = semantic_search.embed_documents(model, searchable)
        st.session_state.device_info = str(model.device)

    st.session_state.current_depth = "evidence_search"


def _render_timeline(utts, spks, candidate):
    for u in sorted(utts, key=lambda u: u.start_at_ms):
        st.markdown(f"`{_fmt(u.start_at_ms)}` **{_spk_role(u.speaker, spks, candidate)}**  {u.text}")


# ── Depth 3: 근거 찾기 ──────────────────────────────────


def _render_evidence_search():
    if st.button("← 화자 선택 변경"):
        st.session_state.current_depth = "speaker_review"
        st.rerun()

    model = _load_model()
    if model is None:
        st.info("모델이 준비되지 않았습니다. `python scripts/prepare_model.py`를 실행하세요.")
        return

    spks = st.session_state.speakers
    cand = st.session_state.candidate_speaker
    st.caption(f"현재 선택: {_spk_role(cand, spks, cand)}")
    if st.session_state.device_info:
        st.caption(f"검색 모델 실행 장치: {st.session_state.device_info.upper()}")

    # 질의
    st.markdown("#### 확인할 내용을 입력하세요")
    query = st.text_input(
        "확인할 내용을 입력하세요",
        placeholder="예: 실패 원인을 어떻게 분석하고 개선했는가?",
        help="한 번에 한 가지 기준을 입력하세요. 같은 전사 결과에서 다시 검색할 수 있습니다.",
        label_visibility="collapsed",
    )

    can_search = bool(query) and st.session_state.doc_embeddings is not None
    if st.session_state.doc_embeddings is None:
        segs = st.session_state.segments
        if segs and not any(s.searchable for s in segs):
            st.warning("검색 가능한 답변 구간이 없습니다.")

    if st.button("관련 답변 찾기", type="primary", disabled=not can_search):
        with st.spinner("관련 답변을 찾고 있습니다."):
            q_emb = semantic_search.embed_query(model, query)
            top_k = semantic_search.search_top_k(q_emb, st.session_state.doc_embeddings)
            searchable_segs = [s for s in st.session_state.segments if s.searchable]
            results = []
            for rank, (idx, sim) in enumerate(top_k, 1):
                seg = searchable_segs[idx]
                results.append({
                    "rank": rank, "similarity": sim, "text": seg.text,
                    "start_at_ms": seg.start_at_ms, "end_at_ms": seg.end_at_ms,
                    "source_utterance_indexes": seg.source_utterance_indexes,
                })
            st.session_state.query = query
            st.session_state.search_results = results
            st.session_state.selected_result_index = None
            st.rerun()

    # 결과
    results = st.session_state.search_results
    if results is None:
        return

    st.markdown(f"#### 찾아볼 만한 답변 {len(results)}개")
    st.markdown(
        '<p class="note">입력한 기준과 의미가 가까운 순서로 표시했습니다. '
        "필요한 판단은 원문과 원음을 확인한 뒤 내려주세요.</p>",
        unsafe_allow_html=True,
    )

    for r in results:
        _render_result_card(r)

    # 상세 layer
    if st.session_state.selected_result_index is not None:
        _render_detail()

    # 다운로드
    st.markdown("---")
    payload = exporters.build_export_payload(
        audio_filename=st.session_state.audio_filename,
        query=st.session_state.query,
        candidate_speaker=cand,
        results=results,
    )
    st.download_button(
        "현재 검색 결과 내려받기",
        data=exporters.serialize_export(payload),
        file_name="search_results.json",
        mime="application/json",
        help="전체 전사 내용과 음성 파일은 포함되지 않습니다.",
    )


def _render_result_card(r):
    rank = r["rank"]
    tr = f"{_fmt(r['start_at_ms'])}–{_fmt(r['end_at_ms'])}"
    with st.container(border=True):
        st.markdown(f"**#{rank}** &nbsp;&nbsp; {tr}")
        text = r["text"]
        st.markdown(text[:150] + "…" if len(text) > 150 else text)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("이 구간 듣기", key=f"listen_{rank}"):
                st.session_state.selected_result_index = rank - 1
                st.rerun()
        with c2:
            if st.button("전사 문맥 보기", key=f"context_{rank}"):
                st.session_state.selected_result_index = rank - 1
                st.rerun()


def _render_detail():
    idx = st.session_state.selected_result_index
    results = st.session_state.search_results
    if idx >= len(results):
        return

    r = results[idx]
    st.markdown("---")
    st.markdown("#### 선택한 답변")
    st.markdown(f"**{_fmt(r['start_at_ms'])}–{_fmt(r['end_at_ms'])}**")

    # 오디오
    audio = st.session_state.audio_bytes
    dur = st.session_state.audio_duration_sec
    if audio is not None and dur is not None:
        s, e = segments.compute_playback_bounds(r["start_at_ms"], r["end_at_ms"], dur)
        st.caption(f"재생 범위 {_fmt(s * 1000)}–{_fmt(e * 1000)}")
        st.audio(audio, start_time=s, end_time=e)

    st.markdown(r["text"])

    # 문맥
    st.markdown("**앞뒤 대화 함께 보기**")
    utts = st.session_state.utterances
    cand = st.session_state.candidate_speaker
    spks = st.session_state.speakers
    prev = _prev_interviewer(utts, r["source_utterance_indexes"], cand)
    if prev is not None:
        st.markdown(f'**{_spk_role(prev.speaker, spks, cand)}** "{prev.text}"')
    st.markdown(f'**{_spk_role(cand, spks, cand)}** "{r["text"]}"')

    with st.expander("검색 정보"):
        st.markdown(f"코사인 유사도: {r['similarity']}")
        st.markdown(f"원본 발화 인덱스: {r['source_utterance_indexes']}")

    if st.button("닫기"):
        st.session_state.selected_result_index = None
        st.rerun()


# ── main ─────────────────────────────────────────────────


def main():
    load_dotenv()
    st.set_page_config(page_title="Interview Evidence", layout="wide")
    _inject_css()
    _check_credentials()
    _init_state()
    _render_depth_bar()

    depth = st.session_state.current_depth
    if depth == "audio_setup":
        _render_audio_setup()
    elif depth == "speaker_review":
        _render_speaker_review()
    elif depth == "evidence_search":
        _render_evidence_search()


if __name__ == "__main__":
    main()
