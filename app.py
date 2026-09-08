import io
import os
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Questionnaire Response Engine", layout="wide")

API = os.environ.get("API_URL", "http://127.0.0.1:8000")
DEFAULT_THRESHOLD = 0.5
TIMEOUT = 600


def api_get(path):
    return httpx.get(f"{API}{path}", timeout=TIMEOUT)


def api_post(path, **kwargs):
    return httpx.post(f"{API}{path}", timeout=TIMEOUT, **kwargs)


def badge(confidence, threshold):
    if confidence >= max(threshold, 0.8):
        return "green"
    if confidence >= threshold:
        return "orange"
    return "red"


def show_citations(citations):
    for c in citations:
        st.caption(f"[{c['n']}] {c['source']} #{c['id']} — {c['label']}")


def single_question(extractive, threshold):
    question = st.text_area("Question", height=90,
                            placeholder="How quickly must I report a security incident?")
    if not st.button("Draft answer", type="primary") or not question.strip():
        return

    with st.spinner("Searching..."):
        response = api_post("/ask", json={"question": question, "extractive": extractive})

    if response.status_code != 200:
        st.error(response.json().get("detail", response.text))
        return

    result = response.json()
    result["text"] = result["answer"]
    colour = badge(result["confidence"], threshold)
    st.markdown(f":{colour}[**confidence {result['confidence']:.3f}**]")
    if result["abstained"]:
        st.warning("Not enough evidence in the corpus. A human needs to write this one.")
    else:
        st.write(result["text"])
    show_citations(result["citations"])


def process_upload(upload, extractive):
    response = api_post(
        "/questionnaire",
        params={"extractive": extractive},
        files={"file": (upload.name, upload.getvalue())},
    )
    if response.status_code != 200:
        st.error(response.json().get("detail", response.text))
        return None

    body = response.json()
    return [
        {
            "control_id": "",
            "question": d["question"],
            "draft": "" if d["abstained"] else d["answer"],
            "confidence": d["confidence"],
            "abstained": d["abstained"],
            "citations": d["citations"],
            "edited": None,
        }
        for d in body["drafts"]
    ]


def export(drafts):
    frame = pd.DataFrame([
        {
            "Control ID": d["control_id"],
            "Question": d["question"],
            "Answer": d["edited"] if d["edited"] is not None else d["draft"],
            "Confidence": round(d["confidence"], 3),
            "Needs review": "yes" if d["abstained"] else "",
        }
        for d in drafts
    ])
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


def questionnaire_tab(extractive, threshold):
    upload = st.file_uploader("Questionnaire", type=["xlsx", "xls", "csv"])

    if upload and st.button("Draft all answers", type="primary"):
        with st.spinner("Drafting every question..."):
            drafts = process_upload(upload, extractive)
        if drafts is not None:
            st.session_state.drafts = drafts
            st.session_state.name = upload.name

    drafts = st.session_state.get("drafts")
    if not drafts:
        st.info("Upload a questionnaire and press *Draft all answers*.")
        return

    flagged = sum(d["abstained"] for d in drafts)
    a, b, c = st.columns(3)
    a.metric("Questions", len(drafts))
    b.metric("Drafted", len(drafts) - flagged)
    c.metric("Need a human", flagged)

    only_flagged = st.toggle("Show only the ones needing review")

    for i, d in enumerate(drafts):
        if only_flagged and not d["abstained"]:
            continue

        colour = badge(d["confidence"], threshold)
        title = f":{colour}[{d['control_id'] or i + 1}] — {d['question'][:80]}"
        with st.expander(title, expanded=d["abstained"]):
            st.markdown(f"**{d['question']}**")
            if d["abstained"]:
                st.warning("No supporting evidence found. Write this one yourself.")
            edited = st.text_area(
                "Answer", value=d["edited"] if d["edited"] is not None else d["draft"],
                key=f"edit_{i}", height=130,
            )
            if edited != d["draft"]:
                d["edited"] = edited
            st.caption(f"confidence {d['confidence']:.3f}")
            show_citations(d["citations"])

    st.download_button(
        "Download completed questionnaire",
        data=export(drafts),
        file_name=f"answered_{Path(st.session_state.name).stem}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


st.title("Questionnaire Response Engine")

with st.sidebar:
    st.header("Settings")
    extractive = st.checkbox("Extractive mode (no LLM, no cost)", value=True)
    threshold = st.slider("Confidence threshold", 0.0, 1.0, DEFAULT_THRESHOLD, 0.05)
    st.caption("Below this, an answer is flagged for a human.")

    try:
        health = api_get("/health").json()
        st.success(f"API up — {health['answer_bank']} answers, {health['policy_chunks']} chunks")
    except httpx.HTTPError:
        st.error(f"API not reachable at {API}. Start it with:\n\n`uvicorn api:app --port 8000`")
        st.stop()

one, many = st.tabs(["Ask one question", "Whole questionnaire"])
with one:
    single_question(extractive, threshold)
with many:
    questionnaire_tab(extractive, threshold)
