# Label Lag Sentinel

**Surfaces FAERS adverse-event signals that are missing from the current FDA drug label.**

Adverse events for marketed drugs — especially generics and off-patent products — often show a
statistical signal in the FDA FAERS spontaneous-reporting system long before (or without ever)
appearing in the official label. Label Lag Sentinel is a free, self-serve **pharmacovigilance
decision-support agent** that, for any drug, computes disproportionality (PRR / ROR / chi-square /
Information Component) from live openFDA FAERS data, parses the current DailyMed label, and
**flags the reactions that are statistically flagged yet unlabeled** — the "label gap." A
constrained LLM (via OpenRouter) adds a WHO-UMC + Bradford Hill causality narrative. Everything is
gated behind a mandatory human-review banner.

> Decision-support and education only. Disproportionality is not causation. Not medical, clinical,
> or regulatory advice. Every signal must be reviewed by a qualified pharmacovigilance professional
> (GVP Module IX / FDA 21 CFR Part 11 / EU AI Act limited-risk).

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # paste your OPENROUTER_API_KEY (openrouter.ai/keys)
streamlit run app.py         # open http://localhost:8501
```
You can also paste the OpenRouter key directly in the sidebar. The openFDA key is optional (raises
rate limits). Docker:
```bash
docker build -t label-lag-sentinel .
docker run -p 8501:8501 --env-file .env label-lag-sentinel
```

## What you get
- KPIs incl. the headline **UNLABELED signals** count.
- A disproportionality **volcano plot** (log2 PRR vs chi-square, sized by case count, colored by
  signal/labeled status).
- A ranked **label-gap table** (PRR/ROR with 95% CIs, chi-square, IC) + bar chart.
- An **LLM causality narrative** (WHO-UMC categories + Bradford Hill), constrained to the numbers.
- CSV export of the full signal table.

## How it works (multi-agent, Pattern E)
`Coordinator` -> RxNorm Resolver -> FAERS Retriever (openFDA) -> Signal Detector (PRR/ROR/chi2/IC)
-> Label Parser (DailyMed SPL) -> Reconciliation (labeled?) -> Causality Assessor (OpenRouter LLM)
-> Reviewer (compliance banner) -> Dashboard. See `docs/architecture.md` and `docs/api_contract.md`.

## Layout
```
label-lag-sentinel/
├── app.py                         # Streamlit + Plotly dashboard (agent UI)
├── sentinel/
│   ├── config.py                  # env-driven settings (no hardcoded secrets)
│   ├── llm.py                     # OpenRouter client (retry + fallback)
│   ├── tools.py                   # openFDA / DailyMed / RxNorm clients
│   ├── signal.py                  # PRR/ROR/chi2/IC — pure, unit-tested
│   └── orchestrator.py            # Coordinator + specialist agents
├── .claude/skills/pv-signal-detection/SKILL.md
├── docs/                          # DISCOVERY, architecture, api_contract
├── tests/test_signal.py
├── AGENTS.md / CLAUDE.md          # Antigravity + Claude Code native config
├── requirements.txt / .env.example / Dockerfile
```

## Test
```bash
pytest -q
```

## Data & licensing notes
openFDA FAERS, DailyMed SPL, and RxNorm are public. Reaction terms are MedDRA Preferred Terms as
returned by FAERS; this project does not redistribute MedDRA. Validate any signal against primary
sources before use.
