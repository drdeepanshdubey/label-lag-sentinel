---
name: pv-signal-detection
description: >-
  Use when the user wants to check a drug's FAERS adverse-event signals against its current FDA
  label, run disproportionality analysis (PRR/ROR/chi-square/IC), or find adverse reactions that
  are statistically flagged but NOT yet in the label. Trigger on requests like "check FAERS
  signals for <drug>", "what adverse events are unlabeled for <drug>", "run a disproportionality
  analysis on <drug>", "is <reaction> a signal for <drug>", or "label gap for <drug>". Do NOT use
  for prescribing or dosing advice, diagnosing a patient, general "what is this drug" information,
  or interpreting an individual person's symptoms — this skill is population-level pharmacovigilance
  decision-support only and every output must be reviewed by a qualified PV professional.
version: 1.0.0
---

# Pharmacovigilance Signal Detection (Label-Gap)

## When this applies (positive triggers)
- "Check FAERS signals for metformin against the label."
- "Find unlabeled adverse events for atorvastatin."
- "Run a disproportionality analysis (PRR/ROR) for ondansetron."
- "Is rhabdomyolysis a disproportionate signal for this drug, and is it labeled?"
- "Show me the label gap / post-market safety signals for <drug>."

## When this does NOT apply (negative triggers — refuse or redirect)
- "What dose of <drug> should this patient take?" -> dosing/prescribing; out of scope.
- "Diagnose why I have this side effect." -> individual clinical care; out of scope.
- "Give me a general overview of <drug>." -> not signal detection; use general info, not this skill.
- "Is it safe for me to take <drug> with <drug>?" -> personal medical advice; out of scope.
- "Predict adverse events for a drug not yet on the market." -> no FAERS/label data; out of scope.

## This is decision-support, not a determination
Disproportionality quantifies whether an event is reported *more than expected* in FAERS — it is
HYPOTHESIS-GENERATING. It is not causation, not incidence, and not a regulatory or clinical
conclusion. FAERS has reporting bias, duplicates, missing data, and no exposure denominator. Do
not let the user treat output as proof of harm or as medical advice. Always keep the human-review
banner. A qualified pharmacovigilance professional must adjudicate before any action.

## How to run
Invoke the Coordinator in `sentinel/orchestrator.py` (or the dashboard `app.py`). Pipeline:
1. Resolve the drug via RxNorm (normalize + gather synonyms).
2. Retrieve FAERS profile via openFDA (N_drug, DB total, top-K reactions).
3. Compute PRR/ROR/chi-square/IC per reaction (`sentinel/signal.py`). Signal = PRR>=2 AND
   chi2>=4 AND a>=3 (MHRA/EMA-style; thresholds are configurable).
4. Parse the current DailyMed label (Adverse Reactions / Warnings / Boxed Warning sections).
5. Reconcile -> flag each signal labeled vs unlabeled. The unlabeled signals are the deliverable.
6. LLM causality narrative (WHO-UMC + Bradford Hill) constrained strictly to the supplied numbers.

## Output
A signal table (per-reaction PRR/ROR/chi2/IC with CIs + labeled flag), a ranked list of unlabeled
signals, a disproportionality plot, and an evidence-bound causality narrative — all under the
mandatory human-review banner. Rendered by the Streamlit dashboard (`app.py`).

## Guardrails (must hold)
- No secrets in code; keys via .env/sidebar only.
- External calls: timeout + retry/backoff + LLM model fallback.
- LLM must never fabricate case facts, numbers, or dates beyond the provided rows.
- Never phrase results as clinical advice, incidence, or a regulatory determination.
