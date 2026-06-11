"""Tests for the TaxKittie 3-НДФЛ tax engine."""

import importlib.util
import os
import sys
from datetime import date
from importlib.machinery import SourceFileLoader

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "taxkittie")
_spec = importlib.util.spec_from_loader("taxkittie", SourceFileLoader("taxkittie", _PATH))
tk = importlib.util.module_from_spec(_spec)
sys.modules["taxkittie"] = tk          # so @dataclass can resolve the module globals
_spec.loader.exec_module(tk)

TaxReturn, Taxpayer, compute = tk.TaxReturn, tk.Taxpayer, tk.compute
ndfl_on_base, professional_deduction = tk.ndfl_on_base, tk.professional_deduction

# Fictional taxpayer — no real personal data.
TP = Taxpayer("Петров", "Пётр", "Петрович", "770000000000",
              ogrnip="000000000000000", tax_authority_code="7701")


def test_income_case():
    # 1 000 000 − 20 % проф. вычет = 800 000 база; × 13 % = 104 000.
    r = compute(TaxReturn(2023, TP, income=1_000_000))
    assert r.professional_deduction == 200_000
    assert r.tax_base == 800_000
    assert r.ndfl == 104_000
    assert r.tax_due == 104_000


def test_nil_year():
    r = compute(TaxReturn(2024, TP, income=0))
    assert r.ndfl == 0
    assert r.tax_due == 0


def test_professional_deduction_prefers_larger():
    assert professional_deduction(TaxReturn(2023, TP, income=100_000, documented_expenses=10_000)) == 20_000
    assert professional_deduction(TaxReturn(2023, TP, income=100_000, documented_expenses=60_000)) == 60_000


def test_progressive_2023_over_5m():
    # 5M × 13 % + 1M × 15 % = 800 000.
    assert ndfl_on_base(6_000_000, 2023) == 800_000


def test_progressive_2025_brackets():
    # 2.4M × 13 % + 0.6M × 15 % = 402 000.
    assert ndfl_on_base(3_000_000, 2025) == 402_000


def test_fine_119_nil_is_minimum():
    r = compute(TaxReturn(2024, TP, income=0), filing_date=date(2026, 6, 15))
    assert r.fine_119 == 1_000


def test_fine_119_capped_at_30pct():
    r = compute(TaxReturn(2023, TP, income=1_000_000), filing_date=date(2026, 6, 15))
    assert r.fine_119 == round(104_000 * 0.30)  # 31200


def test_fine_122_avoided_when_paid_before_filing():
    r = compute(TaxReturn(2023, TP, income=1_000_000),
                filing_date=date(2026, 6, 15), paid_before_filing=True)
    assert r.fine_122 == 0


def test_peni_accrues_when_overdue():
    r = compute(TaxReturn(2023, TP, income=1_000_000), payment_date=date(2026, 6, 15))
    assert r.peni > 0


if __name__ == "__main__":
    import sys
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
