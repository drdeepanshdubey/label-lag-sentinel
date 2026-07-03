"""Label Lag Sentinel — interactive pharmacovigilance dashboard (Streamlit + Plotly).

Run:  streamlit run app.py
The dashboard IS the agent's UI: it drives the multi-agent Coordinator and renders the
FAERS-vs-label gap analysis. Safety output is gated behind a mandatory human-review banner.
"""
from __future__ import annotations
import math
import pandas as pd
import streamlit as st
import plotly.express as px

from sentinel import get_settings, Coordinator, OpenRouterLLM, LLMError

st.set_page_config(page_title="Label Lag Sentinel", page_icon="alert", layout="wide")

st.title("Label Lag Sentinel")
st.caption("Surfaces FAERS adverse-event signals that are NOT in the current FDA label "
           "(openFDA FAERS + DailyMed + RxNorm, causality via OpenRouter LLM).")

s = get_settings()

with st.sidebar:
    st.header("Configuration")
    key = st.text_input("OpenRouter API key", value=s.openrouter_api_key, type="password",
                        help="Get one at openrouter.ai/keys. Used only for the causality narrative.")
    model = st.text_input("OpenRouter model", value=s.openrouter_model)
    s.openrouter_api_key = key.strip()
    s.openrouter_model = model.strip()
    st.divider()
    drug = st.text_input("Drug (generic name preferred)", value="metformin")
    top_k = st.slider("Top FAERS reactions to analyze", 5, 50, 20, 5)
    st.markdown("**Signal criteria (MHRA/EMA-style)**")
    prr_min = st.number_input("PRR >=", 1.0, 10.0, 2.0, 0.5)
    chi2_min = st.number_input("chi-square >=", 0.0, 20.0, 4.0, 1.0)
    a_min = st.number_input("min case count (a) >=", 1, 20, 3, 1)
    run = st.button("Run signal analysis", type="primary", use_container_width=True)

banner_slot = st.container()

if run and drug.strip():
    llm = None
    if s.openrouter_api_key:
        try:
            llm = OpenRouterLLM(s)
        except LLMError as e:
            st.warning(str(e))
    logbox = st.status("Running multi-agent pipeline...", expanded=True)
    coord = Coordinator(s, llm=llm, log=lambda m: logbox.write(m))
    try:
        res = coord.run(drug.strip(), top_k=int(top_k), prr_min=float(prr_min),
                        chi2_min=float(chi2_min), a_min=int(a_min))
        logbox.update(label="Pipeline complete", state="complete", expanded=False)
        st.session_state["res"] = res
    except Exception as e:
        logbox.update(label="Pipeline failed", state="error")
        st.error(f"Error: {e}")
        st.stop()

res = st.session_state.get("res")
if res:
    with banner_slot:
        st.warning(res.review_banner)

    df = res.signals
    n_signals = int(df["is_signal"].sum()) if (not df.empty and "is_signal" in df.columns) else 0
    n_unlabeled = len(res.unlabeled_signals)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Resolved drug", res.resolved_drug)
    c2.metric("FAERS reports (drug)", f"{res.n_drug:,}")
    c3.metric("Reactions analyzed", len(df))
    c4.metric("Statistical signals", n_signals)
    c5.metric("UNLABELED signals", n_unlabeled, delta="label gap", delta_color="inverse")

    st.caption(f"Current label: {res.label_title or '-'}  |  sections parsed: "
               f"{', '.join(res.labeled_sections.keys()) or 'none found'}")

    if df.empty:
        st.info("No reactions returned from FAERS for this drug / snapshot.")
        st.stop()

    st.subheader("Disproportionality landscape")
    plot_df = df.copy()
    plot_df["log2_prr"] = plot_df["prr"].apply(lambda v: math.log2(v) if v and v > 0 else 0.0)
    plot_df["status"] = plot_df.apply(
        lambda r: "Signal - UNLABELED" if (r["is_signal"] and not r["labeled"])
        else ("Signal - labeled" if r["is_signal"] else "Not a signal"), axis=1)
    fig = px.scatter(
        plot_df, x="log2_prr", y="chi2", size="a", color="status", hover_name="reaction",
        hover_data={"prr": True, "ror": True, "a": True, "log2_prr": False},
        color_discrete_map={"Signal - UNLABELED": "#e63946", "Signal - labeled": "#457b9d",
                            "Not a signal": "#adb5bd"},
        labels={"log2_prr": "log2(PRR)  ->  disproportionality", "chi2": "chi-square (strength)"})
    fig.add_hline(y=float(chi2_min), line_dash="dash", line_color="grey")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Potential label-gap signals (statistical signal, absent from current label)")
    if res.unlabeled_signals.empty:
        st.success("No unlabeled signals crossed the threshold — every detected signal "
                   "appears in the current label (or no label was found).")
    elif "priority_score" not in res.unlabeled_signals.columns:
        # Fallback for old cached sessions
        st.warning("Please click 'Run signal analysis' again to generate the new Priority Scores.")
    else:
        show = res.unlabeled_signals[["reaction", "priority_score", "evidence_rationale", "a", "prr", "chi2"]].rename(
            columns={"a": "cases", "priority_score": "Priority Score", "evidence_rationale": "Evidence Rationale"})
        st.dataframe(show, use_container_width=True, hide_index=True, column_config={
            "Priority Score": st.column_config.ProgressColumn(
                "Priority Score",
                help="0-100 score based on FAERS statistical strength + PubMed case report corroboration",
                format="%d",
                min_value=0,
                max_value=100,
            )
        })
        top_bar = res.unlabeled_signals.head(12)
        bar = px.bar(top_bar, x="priority_score", y="reaction", orientation="h", color="pubmed_cases",
                     color_continuous_scale="Reds", labels={"priority_score": "Priority Score", "reaction": "", "pubmed_cases": "Literature Cases"})
        bar.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(bar, use_container_width=True)

    with st.expander("Full signal table (all analyzed reactions)"):
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Causality assessment (LLM — WHO-UMC + Bradford Hill)")
    st.markdown(res.narrative)

    st.divider()
    st.download_button("Download full signal table (CSV)",
                       df.to_csv(index=False).encode(),
                       f"{res.resolved_drug}_faers_signals.csv", "text/csv")

st.divider()
st.caption("Data: openFDA FAERS, DailyMed SPL, RxNorm (all public). LLM via OpenRouter. "
           "Research / educational decision-support only — not medical or regulatory advice.")
