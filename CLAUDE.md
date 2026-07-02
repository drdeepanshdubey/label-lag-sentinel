# CLAUDE.md — Label Lag Sentinel

Canonical engineering instructions live in **AGENTS.md** (single source of truth for run, test,
architecture, data sources, and constraints). Read it first.

## TL;DR for Claude Code
- Purpose: reconcile FAERS disproportionality vs the current DailyMed label; surface unlabeled signals.
- Entry point: `streamlit run app.py`. Core logic: `sentinel/orchestrator.py`.
- Domain skill: `.claude/skills/pv-signal-detection/SKILL.md` (auto-loads; defines scope + triggers).
- Tests: `pytest -q`.

## Hard rules (mirror of AGENTS.md — do not violate)
1. No hardcoded secrets — keys from `.env` / sidebar only.
2. External calls need timeout + retry/backoff + fallback.
3. LLM reasons ONLY over supplied quantitative evidence; no fabricated case facts, numbers, or dates.
4. Every safety output shows the human-review banner (GVP IX / 21 CFR Part 11 / EU AI Act limited-risk).
5. Decision-support only — never a regulatory determination or clinical/medical advice.
6. Read-only tools; any future write/notify tool requires an explicit confirmation gate.

## When editing
- Keep `sentinel/signal.py` dependency-free (only stdlib) so the math stays unit-testable offline.
- Keep this file and AGENTS.md under 200 lines.
