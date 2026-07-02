"""Disproportionality analysis — pure functions, no external dependencies (unit-testable).

Implements the standard pharmacovigilance signal metrics on a 2x2 contingency table:
    a = reports with drug AND event      b = reports with drug, NOT event
    c = reports NOT drug, WITH event     d = reports NOT drug, NOT event
PRR / ROR with 95% CI, Yates-corrected chi-square, and a BCPNN-style Information Component.
Signal rule follows the widely used MHRA/EMA criteria: PRR>=2 AND chi2>=4 AND a>=3.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, asdict


@dataclass
class Disproportionality:
    reaction: str
    a: int
    b: int
    c: int
    d: int
    prr: float
    prr_low: float
    prr_high: float
    ror: float
    ror_low: float
    ror_high: float
    chi2: float
    ic: float
    is_signal: bool

    def to_dict(self) -> dict:
        return asdict(self)


def compute(reaction: str, a: int, b: int, c: int, d: int,
            prr_min: float = 2.0, chi2_min: float = 4.0, a_min: int = 3) -> Disproportionality:
    a, b, c, d = int(a), int(b), int(c), int(d)
    # 0.5 continuity correction for ratio point estimates & CIs (avoids divide-by-zero)
    ah, bh, ch, dh = a + 0.5, b + 0.5, c + 0.5, d + 0.5

    # Proportional Reporting Ratio + 95% CI (log method)
    prr = (ah / (ah + bh)) / (ch / (ch + dh))
    se_prr = math.sqrt(1 / ah - 1 / (ah + bh) + 1 / ch - 1 / (ch + dh))
    prr_low, prr_high = prr * math.exp(-1.96 * se_prr), prr * math.exp(1.96 * se_prr)

    # Reporting Odds Ratio + 95% CI (log method)
    ror = (ah * dh) / (bh * ch)
    se_ror = math.sqrt(1 / ah + 1 / bh + 1 / ch + 1 / dh)
    ror_low, ror_high = ror * math.exp(-1.96 * se_ror), ror * math.exp(1.96 * se_ror)

    # Yates-corrected chi-square on the observed 2x2
    n = a + b + c + d
    chi2 = 0.0
    r1, r2, c1, c2 = a + b, c + d, a + c, b + d
    if n > 0 and r1 and r2 and c1 and c2:
        exp = [r1 * c1 / n, r1 * c2 / n, r2 * c1 / n, r2 * c2 / n]
        obs = [a, b, c, d]
        chi2 = sum((max(0.0, abs(o - e) - 0.5) ** 2) / e for o, e in zip(obs, exp) if e > 0)

    # BCPNN-style Information Component (descriptive)
    ic = 0.0
    if n > 0 and r1 and c1:
        p_ae = (a + 0.5) / (n + 1)
        p_a = (r1 + 0.5) / (n + 1)
        p_e = (c1 + 0.5) / (n + 1)
        if p_a * p_e > 0:
            ic = math.log2(p_ae / (p_a * p_e))

    is_signal = (prr >= prr_min and chi2 >= chi2_min and a >= a_min)

    return Disproportionality(
        reaction=reaction, a=a, b=b, c=c, d=d,
        prr=round(prr, 3), prr_low=round(prr_low, 3), prr_high=round(prr_high, 3),
        ror=round(ror, 3), ror_low=round(ror_low, 3), ror_high=round(ror_high, 3),
        chi2=round(chi2, 2), ic=round(ic, 3), is_signal=bool(is_signal),
    )
