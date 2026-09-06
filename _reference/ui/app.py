import os

import httpx
import streamlit as st

API = os.environ.get("QRE_API_URL", "http://127.0.0.1:8000")
CONFIDENCE_BANDS = [(0.7, "🟢"), (0.45, "🟡")]

st.set_page_config(page_title="Questionnaire Response Engine", layout="wide")


def client() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=600)


def badge(confidence: float) -> str:
    for threshold, mark in CONFIDENCE_BANDS:
        if confidence >= threshold:
            return mark
    return "🔴"


def show_citations(citations: list[dict]) -> None:
    if not citations:
        st.caption("No sources retrieved.")
        return
    for c in citations:
        label = c.get("reference") or f"{c['source']} #{c['source_id']}"
        st.markdown(f"**[{c['rank']}] {label}** · `{c['source']}` · {c['score']:.3f}")
        st.caption(c.get("excerpt") or "")


def ask_tab(company: str) -> None:
    question = st.text_area("Question", height=100, placeholder="Do you encrypt data at rest?")
    extractive = st.checkbox("Extractive mode (reuse a past answer, no LLM call)", value=True)

    if not st.button("Draft answer", type="primary") or not question.strip():
        return

    with client() as http, st.spinner("Searching past answers and policies..."):
        response = http.post(
            "/ask",
            json={"question": question, "company": company, "extractive": extractive},
        )

    if response.status_code != 200:
        st.error(response.json().get("detail", response.text))
        return

    body = response.json()
    st.markdown(f"### {badge(body['confidence'])} Draft")
    st.write(body["answer"])
    st.caption(
        f"confidence {body['confidence']:.2f} · status {body['status']} · model {body['model']}"
    )
    with st.expander("Sources", expanded=True):
        show_citations(body["citations"])


def questionnaire_tab(company: str) -> None:
    upload = st.file_uploader("Questionnaire (.xlsx or .csv)", type=["xlsx", "xls", "csv"])
    if upload and st.button("Upload", type="primary"):
        with client() as http:
            response = http.post(
                "/questionnaires",
                data={"company": company},
                files={"file": (upload.name, upload.getvalue())},
            )
        if response.status_code == 201:
            st.success(f"Loaded {response.json()['question_count']} questions")
        else:
            st.error(response.json().get("detail", response.text))

    with client() as http:
        questionnaires = http.get("/questionnaires").json()

    if not questionnaires:
        st.info("Nothing uploaded yet.")
        return

    labels = {f"#{q['id']} · {q['name']} · {q['status']}": q["id"] for q in questionnaires}
    chosen = st.selectbox("Questionnaire", list(labels))
    questionnaire_id = labels[chosen]

    col_a, col_b = st.columns([1, 3])
    with col_a:
        extractive = st.checkbox("Extractive", value=True, key="q_extractive")
        if st.button("Draft all answers"):
            with client() as http, st.spinner("Drafting..."):
                http.post(
                    f"/questionnaires/{questionnaire_id}/process",
                    params={"extractive": extractive},
                )
            st.rerun()

    with client() as http:
        drafts = http.get(f"/questionnaires/{questionnaire_id}/drafts").json()

    if not drafts:
        st.info("No drafts yet. Press *Draft all answers*.")
        return

    needs_review = sum(1 for d in drafts if d["status"] == "needs_review")
    with col_b:
        st.metric("Needs human review", f"{needs_review} / {len(drafts)}")

    only_flagged = st.toggle("Show only answers that need review")
    for draft in drafts:
        if only_flagged and draft["status"] != "needs_review":
            continue

        header = f"{badge(draft['confidence'])} {draft['control_id'] or draft['row_ref']} — "
        with st.expander(header + draft["question"][:90]):
            st.markdown(f"**{draft['question']}**")
            edited = st.text_area(
                "Draft",
                value=draft["edited_text"] or draft["answer"],
                key=f"text_{draft['id']}",
                height=140,
            )
            st.caption(f"confidence {draft['confidence']:.2f} · status {draft['status']}")
            if st.button("Approve", key=f"approve_{draft['id']}"):
                with client() as http:
                    http.post(f"/drafts/{draft['id']}/approve", json={"edited_text": edited})
                st.rerun()
            show_citations(draft["citations"])


st.title("Questionnaire Response Engine")
company = st.sidebar.text_input("Company", value="acme")
try:
    with client() as http:
        http.get("/health").raise_for_status()
except httpx.HTTPError:
    st.error(f"API is not reachable at {API}. Start it with `make api`.")
    st.stop()

ask, questionnaires = st.tabs(["Ask one question", "Questionnaires"])
with ask:
    ask_tab(company)
with questionnaires:
    questionnaire_tab(company)
