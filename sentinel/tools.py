"""Public pharma data clients: openFDA FAERS, DailyMed SPL, RxNorm. Read-only.

Every request has a timeout and 3x exponential backoff. 404 -> None (treated as no data),
429 -> backoff + retry. No secrets are hardcoded; openFDA key (optional) comes from Settings.
"""
from __future__ import annotations
import time
import functools
from typing import Optional, List
import requests
from .config import Settings

_UA = {"User-Agent": "LabelLagSentinel/1.0 (research; pharmacovigilance decision-support)"}


def _get(url: str, params: Optional[dict] = None, timeout: float = 30.0, retries: int = 3):
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=_UA, timeout=timeout)
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(2 ** attempt + 1)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GET failed for {url}: {last_err}")


# ----------------------------- RxNorm / RxNav -----------------------------
def rxnorm_normalize(s: Settings, name: str) -> dict:
    out = {"query": name, "rxcui": None, "name": name, "candidates": [name]}
    r = _get(f"{s.rxnorm_base}/rxcui.json", {"name": name})
    ids = []
    if r is not None:
        ids = (r.json().get("idGroup", {}) or {}).get("rxnormId", []) or []
    if ids:
        out["rxcui"] = ids[0]
    else:
        r = _get(f"{s.rxnorm_base}/approximateTerm.json", {"term": name, "maxEntries": 1})
        if r is not None:
            cand = (r.json().get("approximateGroup", {}) or {}).get("candidate", []) or []
            if cand:
                out["rxcui"] = cand[0].get("rxcui")
                out["name"] = cand[0].get("name", name)
    if out["rxcui"]:
        r = _get(f"{s.rxnorm_base}/rxcui/{out['rxcui']}/allrelated.json")
        cands = {out["name"], name}
        try:
            groups = (r.json().get("allRelatedGroup", {}).get("conceptGroup", []) if r else [])
            for g in groups:
                if g.get("tty") in ("IN", "BN", "PIN", "SBD", "SCD"):
                    for p in (g.get("conceptProperties", []) or []):
                        if p.get("name"):
                            cands.add(p["name"])
        except Exception:
            pass
        out["candidates"] = sorted(cands)[:8]
    return out


# ----------------------------- openFDA FAERS -----------------------------
_DRUG_FIELDS = [
    "patient.drug.openfda.generic_name.exact",
    "patient.drug.medicinalproduct.exact",
    "patient.drug.openfda.brand_name.exact",
]


def _fda_params(s: Settings, **kw) -> dict:
    p = dict(kw)
    if s.openfda_api_key:
        p["api_key"] = s.openfda_api_key
    return p


@functools.lru_cache(maxsize=1)
def _fda_total(base: str, api_key: str) -> int:
    params = {"limit": 1}
    if api_key:
        params["api_key"] = api_key
    r = _get(base, params)
    if not r:
        return 0
    return int(r.json().get("meta", {}).get("results", {}).get("total", 0))


def _fda_count_total(s: Settings, search: str) -> int:
    r = _get(s.openfda_base, _fda_params(s, search=search, limit=1))
    if not r:
        return 0
    return int(r.json().get("meta", {}).get("results", {}).get("total", 0))


def faers_profile(s: Settings, drug_names: List[str], top_k: int = 20) -> dict:
    """Resolve the best-matching FAERS drug field and return N_drug, DB total, top-K reactions."""
    total = _fda_total(s.openfda_base, s.openfda_api_key)
    best = None  # (field, name, n_drug)
    for name in drug_names:
        q = '"%s"' % name.upper()
        for field in _DRUG_FIELDS:
            n = _fda_count_total(s, f"{field}:{q}")
            if n > 0 and (best is None or n > best[2]):
                best = (field, name, n)
        if best:
            break
    if not best:
        return {"ok": False, "reason": "No FAERS reports found for this drug.",
                "total": total, "n_drug": 0, "field": None,
                "drug": drug_names[0] if drug_names else "", "reactions": []}
    field, name, n_drug = best
    q = '"%s"' % name.upper()
    r = _get(s.openfda_base, _fda_params(
        s, search=f"{field}:{q}",
        count="patient.reaction.reactionmeddrapt.exact", limit=top_k))
    reactions = []
    if r is not None:
        for row in r.json().get("results", []):
            if row.get("term"):
                reactions.append({"reaction": row["term"], "a": int(row.get("count", 0))})
    return {"ok": True, "field": field, "drug": name, "n_drug": n_drug,
            "total": total, "reactions": reactions}


def faers_reaction_total(s: Settings, reaction: str) -> int:
    q = '"%s"' % reaction.upper()
    return _fda_count_total(s, f'patient.reaction.reactionmeddrapt.exact:{q}')


# ----------------------------- DailyMed SPL -----------------------------
_AE_LOINCS = {
    "34084-4": "Adverse Reactions",
    "43685-7": "Warnings and Precautions",
    "34071-1": "Warnings",
    "34066-1": "Boxed Warning",
    "42232-9": "Precautions",
}


def dailymed_label(s: Settings, name: str) -> dict:
    r = _get(f"{s.dailymed_base}/spls.json", {"drug_name": name, "pagesize": 1})
    data = (r.json().get("data", []) if r else [])
    if not data:
        return {"ok": False, "setid": None, "title": None, "sections": {}, "full_text": ""}
    setid = data[0].get("setid")
    title = data[0].get("title")
    sections: dict = {}
    x = _get(f"{s.dailymed_base}/spls/{setid}.xml")
    if x is not None:
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(x.content)
            for sec in root.iter():
                tag = sec.tag.split("}")[-1]
                if tag != "section":
                    continue
                code = None
                for ch in sec:
                    if ch.tag.split("}")[-1] == "code":
                        code = ch.get("code")
                        break
                if code in _AE_LOINCS:
                    txt = " ".join(t.strip() for t in sec.itertext() if t and t.strip())
                    key = _AE_LOINCS[code]
                    sections[key] = (sections.get(key, "") + " " + txt).strip()
        except Exception:
            pass
    full = " ".join(sections.values())[:20000]
    return {"ok": True, "setid": setid, "title": title, "sections": sections, "full_text": full}


# ----------------------------- PubMed E-utilities -----------------------------
def pubmed_case_reports(s: Settings, drug: str, reaction: str) -> int:
    """Fetch the number of published case reports for a drug + reaction."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    # [tiab] searches Title and Abstract. [pt] filters by Publication Type.
    query = f'"{drug}"[tiab] AND "{reaction}"[tiab] AND "case reports"[pt]'
    
    r = _get(base, {"db": "pubmed", "term": query, "retmode": "json"}, timeout=10.0)
    if not r:
        return 0
    try:
        data = r.json()
        count = data.get("esearchresult", {}).get("count", 0)
        return int(count)
    except Exception:
        return 0
