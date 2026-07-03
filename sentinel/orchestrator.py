"""Coordinator + specialist agents (Pattern E). Read-only pipeline with human-review gate."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Callable
import pandas as pd
from .config import Settings
from . import tools
from . import signal as sig
from .llm import OpenRouterLLM, LLMError

_CAUSALITY_SYSTEM = (
    "You are a senior pharmacovigilance signal-assessment scientist interpreting quantitative "
    "disproportionality output from the FDA FAERS spontaneous-reporting database. You reason with "
    "the WHO-UMC causality categories (certain / probable / possible / unlikely / conditional / "
    "unassessable) and the Bradford Hill viewpoints (strength, consistency, temporality, biological "
    "gradient, plausibility). You are rigorous and cautious: disproportionality is HYPOTHESIS-"
    "GENERATING, never proof of causation; FAERS has reporting bias, duplicates, and no exposure "
    "denominator. You never fabricate clinical facts, case details, or numbers you were not given. "
    "You always flag that a qualified human must adjudicate. Output concise Markdown."
)


def _norm(t: str) -> str:
    return " ".join(str(t).lower().replace(",", " ").replace("-", " ").split())


@dataclass
class SentinelResult:
    drug_query: str
    resolved_drug: str
    n_drug: int
    total_reports: int
    label_found: bool
    label_title: Optional[str]
    signals: pd.DataFrame
    unlabeled_signals: pd.DataFrame
    labeled_sections: dict
    narrative: str
    review_banner: str
    meta: dict = field(default_factory=dict)


class Coordinator:
    def __init__(self, settings: Settings, llm: Optional[OpenRouterLLM] = None,
                 log: Optional[Callable[[str], None]] = None):
        self.s = settings
        self.llm = llm
        self.log = log or (lambda m: None)

    # ---- agent steps ----
    def resolve(self, drug: str) -> dict:
        self.log(f"RxNorm Resolver: normalizing '{drug}'...")
        return tools.rxnorm_normalize(self.s, drug)

    def retrieve(self, candidates, top_k: int) -> dict:
        self.log("FAERS Retriever: querying openFDA...")
        return tools.faers_profile(self.s, candidates, top_k=top_k)

    def detect(self, profile: dict, prr_min, chi2_min, a_min) -> pd.DataFrame:
        self.log("Signal Detector: computing PRR / ROR / chi2 / IC...")
        rows, N, ND = [], profile["total"], profile["n_drug"]
        for rx in profile["reactions"]:
            E, a = rx["reaction"], rx["a"]
            if not E:
                continue
            NE = tools.faers_reaction_total(self.s, E)
            b = max(ND - a, 0)
            c = max(NE - a, 0)
            d = max(N - ND - NE + a, 0)
            rows.append(sig.compute(E, a, b, c, d, prr_min, chi2_min, a_min).to_dict())
        return pd.DataFrame(rows)

    def parse_label(self, drug: str) -> dict:
        self.log("Label Parser: fetching DailyMed SPL...")
        return tools.dailymed_label(self.s, drug)

    def reconcile(self, signals_df: pd.DataFrame, label: dict) -> pd.DataFrame:
        self.log("Reconciliation: matching signals against the current label...")
        labeled_text = _norm(label.get("full_text", ""))

        def is_labeled(reaction: str) -> bool:
            if not labeled_text:
                return False
            r = _norm(reaction)
            if r and r in labeled_text:
                return True
            toks = [t for t in r.split() if len(t) > 3]
            return bool(toks) and all(t in labeled_text for t in toks)

        if signals_df.empty:
            signals_df["labeled"] = []
            return signals_df
        signals_df["labeled"] = signals_df["reaction"].apply(is_labeled)
        return signals_df

    def prioritize(self, drug: str, unlabeled_df: pd.DataFrame) -> pd.DataFrame:
        if unlabeled_df.empty:
            unlabeled_df = unlabeled_df.copy()
            unlabeled_df["priority_score"] = pd.Series(dtype=int)
            unlabeled_df["pubmed_cases"] = pd.Series(dtype=int)
            unlabeled_df["evidence_rationale"] = pd.Series(dtype=str)
            return unlabeled_df
            
        self.log("Literature Agent: cross-referencing signals with PubMed case reports...")
        
        scores = []
        cases = []
        rationales = []
        
        for _, row in unlabeled_df.iterrows():
            reaction = row["reaction"]
            chi2 = row["chi2"]
            
            n_cases = tools.pubmed_case_reports(self.s, drug, reaction)
            cases.append(n_cases)
            
            stat_score = min(50, int((chi2 / 20.0) * 50))
            if n_cases == 0:
                lit_score = 0
            elif n_cases == 1:
                lit_score = 20
            elif n_cases == 2:
                lit_score = 35
            else:
                lit_score = 50
                
            total_score = stat_score + lit_score
            scores.append(total_score)
            
            rationale = f"Score {total_score}: Stat Signal (Chi2={chi2:.1f})"
            if n_cases > 0:
                rationale += f" + {n_cases} PubMed Case Report{'s' if n_cases > 1 else ''}"
            else:
                rationale += " (No published case reports found)"
            rationales.append(rationale)
            
        unlabeled_df["priority_score"] = scores
        unlabeled_df["pubmed_cases"] = cases
        unlabeled_df["evidence_rationale"] = rationales
        return unlabeled_df.sort_values("priority_score", ascending=False).reset_index(drop=True)

    def assess(self, drug: str, unlabeled_df: pd.DataFrame) -> str:
        if self.llm is None:
            return "_LLM causality assessment skipped — no OpenRouter API key provided._"
        if unlabeled_df.empty:
            return ("No unlabeled disproportionality signals met the threshold for this drug in the "
                    "current FAERS snapshot.")
        self.log("Causality Assessor: LLM applying WHO-UMC + Bradford Hill...")
        top = unlabeled_df.head(10)[["reaction", "a", "prr", "chi2", "priority_score", "pubmed_cases"]]
        table = top.to_string(index=False)
        user = (
            f"Drug: {drug}\n\n"
            "These adverse-event terms show statistical disproportionality in FAERS AND are NOT found "
            "in the drug's current DailyMed label (potential label-gap signals). They have been scored "
            "based on statistical strength and PubMed case report corroboration:\n\n"
            f"{table}\n\n"
            "For the up-to-5 highest-priority terms, provide: (1) a one-line plain-language "
            "interpretation; (2) the WHO-UMC category you would PROVISIONALLY assign given ONLY this "
            "quantitative evidence plus general pharmacology (state your assumptions); (3) which "
            "Bradford Hill viewpoints the data speaks to vs. which need clinical follow-up; (4) a "
            "priority (High/Medium/Low) for human PV review. End with a 2-sentence overall "
            "recommendation. Do not invent case details, dates, or numbers you were not given."
        )
        try:
            return self.llm.chat(_CAUSALITY_SYSTEM, user, temperature=0.2, max_tokens=1400)
        except LLMError as e:
            return f"_LLM assessment unavailable: {e}_"

    def _banner(self) -> str:
        return (
            "DECISION-SUPPORT ONLY — NOT A REGULATORY DETERMINATION. Disproportionality is not "
            "causation. FAERS is a spontaneous-report system with reporting bias, duplicates, and no "
            "exposure denominator. Every signal requires review by a qualified pharmacovigilance "
            "professional before any action (GVP Module IX / FDA 21 CFR Part 11 / EU AI Act "
            "limited-risk decision support)."
        )

    # ---- orchestration ----
    def run(self, drug: str, top_k: int = 20, prr_min: float = 2.0,
            chi2_min: float = 4.0, a_min: int = 3) -> SentinelResult:
        rx = self.resolve(drug)
        profile = self.retrieve(rx["candidates"], top_k)
        if not profile.get("ok"):
            return SentinelResult(
                drug_query=drug, resolved_drug=rx.get("name", drug), n_drug=0,
                total_reports=profile.get("total", 0), label_found=False, label_title=None,
                signals=pd.DataFrame(), unlabeled_signals=pd.DataFrame(), labeled_sections={},
                narrative=f"No FAERS reports found for '{drug}'. Check spelling or try the generic name.",
                review_banner=self._banner(), meta={"reason": profile.get("reason")})
        signals = self.detect(profile, prr_min, chi2_min, a_min)
        label = self.parse_label(profile["drug"])
        signals = self.reconcile(signals, label)
        if not signals.empty:
            signals = signals.sort_values(["is_signal", "prr"], ascending=[False, False]).reset_index(drop=True)
            unlabeled = signals[(signals["is_signal"]) & (~signals["labeled"])].reset_index(drop=True)
            unlabeled = self.prioritize(profile["drug"], unlabeled)
        else:
            unlabeled = signals.copy() if not signals.empty else pd.DataFrame(columns=signals.columns)
            unlabeled["priority_score"] = pd.Series(dtype=int)
            unlabeled["pubmed_cases"] = pd.Series(dtype=int)
            unlabeled["evidence_rationale"] = pd.Series(dtype=str)
        narrative = self.assess(profile["drug"], unlabeled)
        return SentinelResult(
            drug_query=drug, resolved_drug=profile["drug"], n_drug=profile["n_drug"],
            total_reports=profile["total"],
            label_found=bool(label.get("ok") and label.get("full_text")),
            label_title=label.get("title"), signals=signals, unlabeled_signals=unlabeled,
            labeled_sections=label.get("sections", {}), narrative=narrative,
            review_banner=self._banner(),
            meta={"field": profile.get("field"), "rxcui": rx.get("rxcui"),
                  "candidates": rx.get("candidates")})
