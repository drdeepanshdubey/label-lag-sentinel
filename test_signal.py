"""Unit tests for the disproportionality math (no network, no external deps).

signal.py is loaded in isolation so the tests run without installing pandas/openai
(which the package __init__ would otherwise pull in). The module MUST be registered in
sys.modules before exec so dataclass can resolve its __module__.
"""
import importlib.util
import pathlib
import sys

_path = pathlib.Path(__file__).resolve().parents[1] / "sentinel" / "signal.py"
_spec = importlib.util.spec_from_file_location("pv_signal", _path)
sig = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = sig
_spec.loader.exec_module(sig)


def test_known_2x2_is_signal():
    d = sig.compute("NAUSEA", 50, 100, 200, 100000)
    assert d.prr > 2
    assert d.chi2 > 4
    assert d.is_signal is True


def test_low_count_is_not_signal():
    d = sig.compute("HEADACHE", 1, 100, 50, 100000, a_min=3)
    assert d.is_signal is False


def test_ci_ordering():
    d = sig.compute("RASH", 30, 70, 100, 50000)
    assert d.prr_low <= d.prr <= d.prr_high
    assert d.ror_low <= d.ror <= d.ror_high
