# AGENTS.md — Label Lag Sentinel

Pharmacovigilance label-gap agent. Given a drug, it reconciles FAERS adverse-event
disproportionality against the current FDA (DailyMed) label and surfaces statistically
significant reactions that are NOT yet labeled. Decision-support only; multi-agent (Pattern E)
with a mandatory human-review gate.

## Run
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add OPENROUTER_API_KEY
streamlit run app.py          # dashboard + agent UI at http://localhost:8501
```
Docker: `docker build -t label-lag-sentinel . && docker run -p 8501:8501 --env-file .env label-lag-sentinel`

## Test
```
pytest -q                     # disproportionality math (offline)
```

## Architecture (see docs/architecture.md)
Coordinator (`sentinel/orchestrator.py`) dispatches specialist agents:
- RxNorm Resolver -> normalize drug + gather brand/generic synonyms (RxNav).
- FAERS Retriever -> openFDA: N_drug, DB total, top-K reactions (`sentinel/tools.py`).
- Signal Detector -> PRR/ROR/chi2/IC with CIs (`sentinel/signal.py`, pure functions).
- Label Parser -> DailyMed SPL XML, extract Adverse Reactions / Warnings sections.
- Reconciliation -> flag each detected signal labeled vs unlabeled.
- Causality Assessor -> OpenRouter LLM (`sentinel/llm.py`), WHO-UMC + Bradford Hill, evidence-bound.
- Reviewer -> compliance banner + confidence.
- Dashboard/Reporter -> `app.py` (Streamlit + Plotly).

## Skills
`.claude/skills/pv-signal-detection/SKILL.md` is the canonical domain skill (auto-loads in
Claude Code; usable as Antigravity context). It governs when to run signal detection and the
hard scope boundaries.

## Data sources (all free/public)
openFDA FAERS, DailyMed SPL v2, RxNorm/RxNav, OpenRouter (LLM). Endpoints in docs/api_contract.md.

## Constraints (do not violate)
- NO hardcoded secrets. Keys come from `.env` / the sidebar only.
- Every external call has timeout + retry/backoff + (LLM) model fallback.
- The LLM may reason ONLY over the quantitative rows it is given; it must not invent case facts.
- ALL safety output carries the human-review banner. This is not optional (GVP IX / 21 CFR Part 11).
- Disproportionality is hypothesis-generating, never proof of causation. Never phrase output as a
  regulatory determination or clinical advice.
- Read-only tool set; if you add any write/notify tool, it MUST require an explicit confirmation gate.

## Stateless
No database; each query is independent. Caching is in-process only.
