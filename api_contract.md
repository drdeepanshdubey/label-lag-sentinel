# API Contract — Label Lag Sentinel

## openFDA FAERS — https://api.fda.gov/drug/event.json  (free; optional api_key -> 240->1000 req/min)
- Total DB size:      ?limit=1 -> meta.results.total  (cached process-wide)
- Reports for drug:   ?search=<drugfield>:"NAME"&limit=1 -> meta.results.total (= N_drug)
- Top-K reactions:    ?search=<drugfield>:"NAME"&count=patient.reaction.reactionmeddrapt.exact&limit=K
                       -> list of {term, count}; count = a (drug AND event)
- Reports for reaction: ?search=patient.reaction.reactionmeddrapt.exact:"PT"&limit=1 -> total (= N_E)
- Drug fields tried in order (first with >0 hits wins, kept consistent for a & N_drug):
  patient.drug.openfda.generic_name.exact -> patient.drug.medicinalproduct.exact ->
  patient.drug.openfda.brand_name.exact
- Errors: 404 -> treated as zero; 429 -> backoff+retry; timeout 30s, 3 retries.

## DailyMed SPL v2 — https://dailymed.nlm.nih.gov/dailymed/services/v2  (free, no auth)
- Find label:  /spls.json?drug_name=NAME&pagesize=1 -> data[0].setid, title
- Full SPL:    /spls/{setid}.xml -> parse <section> by LOINC code:
  34084-4 Adverse Reactions, 43685-7 Warnings & Precautions, 34071-1 Warnings,
  34066-1 Boxed Warning, 42232-9 Precautions. Section text -> labeled-reaction corpus.

## RxNorm / RxNav — https://rxnav.nlm.nih.gov/REST  (free, no auth)
- Exact:       /rxcui.json?name=NAME -> idGroup.rxnormId
- Fuzzy:       /approximateTerm.json?term=NAME&maxEntries=1
- Synonyms:    /rxcui/{rxcui}/allrelated.json -> IN/BN/PIN/SBD/SCD names (widen FAERS search)

## OpenRouter — https://openrouter.ai/api/v1  (OpenAI-compatible; user key required for LLM step)
- Client: openai SDK, base_url set, HTTP-Referer + X-Title headers.
- Model configurable (OPENROUTER_MODEL); fallback model on error; 3x backoff.
