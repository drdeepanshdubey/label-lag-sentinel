# Architecture — Label Lag Sentinel (Pattern E: multi-agent + human-review gate)

## Pattern
Pattern E (Complex Hybrid) — regulated pharma requires a structural human-review gate, not an
optional one. Coordinator dispatches specialist agents; the final safety output is gated behind
a review banner and an LLM constrained to the supplied quantitative evidence.

## Component map
```
                    +----------------------------------------------+
  drug name  ----->  |  Coordinator (sentinel/orchestrator.py)      |
                    +----------------------------------------------+
                       |        |          |            |        |
                       v        v          v            v        v
             RxNorm Resolver  FAERS      Signal      Label     Reconciliation
             (RxNav)          Retriever  Detector    Parser    (labeled? flag)
                              (openFDA)  (PRR/ROR/    (DailyMed
                                          chi2/IC)    SPL XML)
                                                         |
                                                         v
                                          Causality Assessor (OpenRouter LLM,
                                          WHO-UMC + Bradford Hill, evidence-bound)
                                                         |
                                                         v
                                          Reviewer (confidence + compliance banner)
                                                         |
                                                         v
                              Dashboard / Reporter (app.py — Streamlit + Plotly)
```

## Data flow
1. Resolve drug -> RxNorm rxcui + candidate names (brand/generic) to widen FAERS matching.
2. FAERS: pick the drug field with most reports; get N_drug, total DB N, top-K reactions (a).
3. For each reaction E: fetch N_E; build 2x2 (a,b,c,d); compute PRR/ROR (+95% CI), chi2 (Yates), IC.
4. DailyMed: fetch current SPL, extract Adverse Reactions / Warnings / Boxed-Warning section text.
5. Reconcile: flag each detected signal as labeled/unlabeled via normalized term matching.
6. Unlabeled AND signal -> LLM causality narrative (evidence-bound). Reviewer attaches banner.
7. Dashboard renders KPIs, volcano plot, gap table, narrative, CSV export.

## Security / compliance flow
- Read-only external calls; no write-capable tools -> no destructive gate needed.
- Secrets only via env / sidebar (never persisted). ASI-06 defended.
- Every external call: timeout + 3x exponential backoff + fallback. ASI-08 defended.
- LLM constrained to given quantitative rows; forbidden from inventing case facts. Hallucination control.
- Mandatory human-review banner on all safety output (GVP IX / Part 11 / EU AI Act limited-risk).

## Stateless
No database. Each query is independent; caching is in-process (lru + Streamlit cache). Marked stateless.
