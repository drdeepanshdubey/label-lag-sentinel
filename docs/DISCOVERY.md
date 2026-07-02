# Discovery — Label Lag Sentinel

## Business Problem
Adverse-event signals for marketed drugs (especially generics/off-patent) are detected in FDA
FAERS long before — or without ever — appearing in the drug's official label. A recent FAERS
study found ~61% of statistically flagged drug–event pairs were absent from labeling, with
median detection lags of 18–44 months. There is no free, self-serve tool that continuously
reconciles *live FAERS disproportionality* against the *current DailyMed label* and surfaces the
gap. This is decision-support pharmacovigilance triage that is today done manually or not at all.

## Industry / Domain
Pharmacovigilance & drug safety (post-market surveillance). GVP Module IX (signal management).

## End Users / Personas
- PV / drug-safety associates triaging signals with no enterprise Empirica/Evidex license.
- Regulatory & medical-affairs teams monitoring off-patent portfolios.
- Pharmacy students / academics learning signal detection on real data.

## Expected Outputs
Interactive dashboard + exportable table: per-reaction PRR/ROR/chi2/IC with CIs, a labeled-vs-
unlabeled flag, a ranked "label-gap" signal list, a disproportionality volcano plot, and an
LLM causality narrative (WHO-UMC + Bradford Hill), all behind a mandatory human-review banner.

## Constraints
Free/public data only (openFDA FAERS, DailyMed SPL, RxNorm). LLM via OpenRouter (user key).
Solo-buildable. Regulatory frame: FDA 21 CFR Part 11, ICH E2E, GVP Module IX, EU AI Act
(limited-risk decision support), ISO 42001 posture, MedDRA terms used as returned by FAERS
(no MedDRA redistribution).

## Success Metrics
- Resolves a drug and returns >=1 FAERS reaction profile in <60s (top-20 mode).
- Correctly flags known label-gap examples vs. labeled reactions (face-valid on back-test drugs).
- Disproportionality math unit-tested and reproducible.
- Zero hardcoded secrets; runs with `streamlit run app.py` after `pip install -r requirements.txt`.

## Deployment Target
Both — Antigravity (AGENTS.md + skills dir) is primary per the request; CLAUDE.md included for
Claude Code portability. `.claude/skills/` is the canonical skill source.

## Available APIs (all free / public)
openFDA `/drug/event.json` (FAERS), DailyMed SPL v2, RxNorm/RxNav REST. See api_contract.md.

## Assumptions
FAERS drug/reaction fields are queryable by count; DailyMed exposes SPL XML with LOINC-coded
adverse-reaction/warnings sections; OpenRouter key is OpenAI-compatible.

## Risks
FAERS reporting bias / duplicates / no exposure denominator (disproportionality != causation) ->
mitigated by mandatory review banner + LLM caution prompt. API rate limits -> retry/backoff +
optional openFDA key. Hallucination -> LLM constrained to given quantitative evidence only.
