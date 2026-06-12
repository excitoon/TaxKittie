"""Tests for the TaxKittie tax engine — every regime, both entities, payroll."""

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

Filing, Taxpayer, compute = tk.Filing, tk.Taxpayer, tk.compute
ndfl_on_base, professional_deduction = tk.ndfl_on_base, tk.professional_deduction
ip_contributions, payroll_contributions = tk.ip_contributions, tk.payroll_contributions
payroll_ndfl, build_tree = tk.payroll_ndfl, tk.build_tree
build_book_tex = tk.build_book_tex

# Fictional taxpayers — no real personal data.
IP = Taxpayer("Петров", "Пётр", "Петрович", inn="770000000000",
              ogrnip="000000000000000", tax_authority_code="7701", oktmo="45000000")
ORG = Taxpayer(kind="org", name="ООО «Ромашка»", inn="7700000000", kpp="770001001",
               tax_authority_code="7701", oktmo="45000000")


# ── ОСНО ИП (3-НДФЛ) ──────────────────────────────────────────────────────
def test_osno_ip_income_case():
    # 1 000 000 − 20 % проф. вычет = 800 000 база; × 13 % = 104 000.
    f = Filing(2023, IP, regime="osno", income=1_000_000)
    r = compute(f)
    assert professional_deduction(f) == 200_000
    assert r.tax_base == 800_000
    assert r.tax == 104_000
    assert r.tax_due == 104_000


def test_osno_ip_nil_year():
    r = compute(Filing(2024, IP, regime="osno", income=0))
    assert r.tax == 0 and r.tax_due == 0


def test_professional_deduction_prefers_larger():
    assert professional_deduction(Filing(2023, IP, income=100_000, expenses=10_000)) == 20_000
    assert professional_deduction(Filing(2023, IP, income=100_000, expenses=60_000)) == 60_000


def test_progressive_2023_over_5m():
    assert ndfl_on_base(6_000_000, 2023) == 800_000          # 5M×13 % + 1M×15 %


def test_progressive_2025_brackets():
    assert ndfl_on_base(3_000_000, 2025) == 402_000          # 2.4M×13 % + 0.6M×15 %


# ── penalties (ст. 75 / 119 / 122) ────────────────────────────────────────
def test_fine_119_nil_is_minimum():
    r = compute(Filing(2024, IP, regime="osno", income=0), filing_date=date(2026, 6, 15))
    assert r.fine_119 == 1_000


def test_fine_119_capped_at_30pct():
    r = compute(Filing(2023, IP, regime="osno", income=1_000_000), filing_date=date(2026, 6, 15))
    assert r.fine_119 == round(104_000 * 0.30)               # 31200


def test_fine_122_avoided_when_paid_before_filing():
    r = compute(Filing(2023, IP, regime="osno", income=1_000_000),
                filing_date=date(2026, 6, 15), paid_before_filing=True)
    assert r.fine_122 == 0


def test_peni_accrues_when_overdue():
    r = compute(Filing(2023, IP, regime="osno", income=1_000_000), payment_date=date(2026, 6, 15))
    assert r.peni > 0


# ── УСН ────────────────────────────────────────────────────────────────────
def test_usn_dohody_reduced_by_contributions_ip_no_employees():
    # 3M × 6 % = 180 000; ИП без работников уменьшает на взносы (53 658 + 1 %·2,7M = 80 658).
    r = compute(Filing(2025, IP, regime="usn", usn_object="dohody", income=3_000_000))
    assert r.tax == 180_000
    assert r.reduction == 80_658
    assert r.tax_due == 99_342


def test_usn_dohody_ip_with_employees_capped_at_50pct():
    r = compute(Filing(2025, IP, regime="usn", usn_object="dohody",
                       income=1_000_000, employees=[100_000]))
    assert r.tax == 60_000
    assert r.reduction == 30_000                              # capped at 50 %
    assert r.tax_due == 30_000


def test_usn_dohody_rashody_minimum_tax():
    # base 10 000 × 15 % = 1 500, but минимальный налог = 1 % · 1 000 000 = 10 000 wins.
    r = compute(Filing(2025, IP, regime="usn", usn_object="dohody-rashody",
                       income=1_000_000, expenses=990_000))
    assert r.tax == 10_000


def test_usn_vat_kicks_in_above_60m_from_2025():
    r = compute(Filing(2025, ORG, regime="usn", usn_object="dohody", income=100_000_000))
    assert r.vat == round(100_000_000 * 0.05)                 # 5 % band, 60–250M
    r24 = compute(Filing(2024, ORG, regime="usn", usn_object="dohody", income=100_000_000))
    assert r24.vat == 0                                       # rule is 2025+


def test_org_has_no_self_contributions():
    r = compute(Filing(2025, ORG, regime="usn", usn_object="dohody", income=1_000_000))
    assert r.contributions_self == 0


# ── ОСНО ООО (налог на прибыль) ───────────────────────────────────────────
def test_profit_tax_25pct_from_2025():
    r = compute(Filing(2025, ORG, regime="osno", income=8_000_000, expenses=5_000_000))
    assert r.tax_base == 3_000_000
    assert r.tax == 750_000                                   # 3M × 25 %
    assert r.vat == 1_600_000                                 # 8M × 20 %


def test_profit_tax_20pct_through_2024():
    r = compute(Filing(2024, ORG, regime="osno", income=8_000_000, expenses=5_000_000))
    assert r.tax == 600_000                                   # 3M × 20 %


# ── ПСН / АУСН / НПД / ЕСХН ────────────────────────────────────────────────
def test_psn_cost_and_contribution_reduction():
    # patent 1M × 6 % = 60 000; ИП без работников уменьшает взносами до нуля.
    r = compute(Filing(2025, IP, regime="psn", potential_income=1_000_000))
    assert r.tax == 60_000
    assert r.tax_due == 0


def test_ausn_dohody_no_contributions():
    r = compute(Filing(2025, IP, regime="ausn", usn_object="dohody", income=1_000_000))
    assert r.tax == 80_000                                    # 8 %
    assert r.contributions_self == 0                          # АУСН: no взносы


def test_npd_split_rates():
    r = compute(Filing(2025, IP, regime="npd", income=1_000_000, income_from_legal=400_000))
    assert r.tax == 48_000                                    # 600k×4 % + 400k×6 %


def test_eshn_six_percent():
    r = compute(Filing(2025, IP, regime="eshn", income=1_000_000, expenses=400_000))
    assert r.tax == 36_000                                    # 600k × 6 %


# ── payroll ────────────────────────────────────────────────────────────────
def test_payroll_contributions_under_base_limit():
    assert payroll_contributions([100_000], 2025) == 360_000  # 1.2M × 30 %


def test_payroll_contributions_msp_split():
    # 2025 МРОТ 22 440 → 1.5× = 33 660; 33 660×30 % + 66 340×15 % = 20 049 /mo × 12.
    assert payroll_contributions([100_000], 2025, msp=True) == 240_588


def test_payroll_ndfl_withheld():
    assert payroll_ndfl([100_000], 2025) == 156_000           # 1.2M × 13 %


def test_ip_contributions_caps_extra():
    fixed, extra = ip_contributions(2025, 50_000_000)
    assert fixed == 53_658
    assert extra == 300_888                                   # 1 % part capped


# ── regime / entity validation ────────────────────────────────────────────
def test_psn_rejected_for_org():
    try:
        compute(Filing(2025, ORG, regime="psn", potential_income=1_000_000))
    except ValueError:
        return
    raise AssertionError("expected ПСН to be rejected for an ООО")


# ── XML ────────────────────────────────────────────────────────────────────
def test_ndfl_xml_builds():
    f = Filing(2023, IP, regime="osno", income=1_000_000)
    root = build_tree(f, compute(f), doc_date=date(2026, 6, 12))
    assert root.find("Документ").get("КНД") == "1151020"


def test_usn_xml_builds_for_org():
    f = Filing(2025, ORG, regime="usn", usn_object="dohody", income=3_000_000)
    root = build_tree(f, compute(f), doc_date=date(2026, 6, 12))
    assert root.find("Документ").get("КНД") == "1152017"


def test_no_xml_for_psn():
    f = Filing(2025, IP, regime="psn", potential_income=1_000_000)
    try:
        build_tree(f, compute(f), doc_date=date(2026, 6, 12))
    except ValueError:
        return
    raise AssertionError("expected no XML builder for ПСН")


# ── КУДиР / books (LaTeX) ──────────────────────────────────────────────────
def test_book_psn_is_income_only():
    f = Filing(2026, IP, regime="psn", income=500_000, potential_income=1_000_000)
    tex = build_book_tex(f, [], doc_date=date(2026, 6, 12))
    assert "патентную систему" in tex
    assert "Расходы" not in tex                       # ПСН book has no expense column
    assert "500\\,000,00" in tex


def test_book_usn_has_expense_column():
    f = Filing(2026, IP, regime="usn", usn_object="dohody-rashody",
               income=1_000_000, expenses=400_000)
    tex = build_book_tex(f, [], doc_date=date(2026, 6, 12))
    assert "упрощённую систему" in tex
    assert "Расходы" in tex


def test_book_osno_is_86n_with_ndfl_note():
    f = Filing(2023, IP, regime="osno", income=252_700)
    tex = build_book_tex(f, [], doc_date=date(2023, 1, 1))
    assert "хозяйственных операций" in tex
    assert "НДФЛ" in tex and "252\\,700,00" in tex


def test_book_operations_render_and_total():
    f = Filing(2023, IP, regime="osno", income=300_000)
    ops = [tk._operation("2023-10-01;№5;Оплата услуг;200000;0"),
           tk._operation("2023-11-01;№6;Оплата услуг;100000;0")]
    tex = build_book_tex(f, ops, doc_date=date(2023, 1, 1))
    assert "Оплата услуг" in tex
    assert "300\\,000,00" in tex                       # 200000 + 100000 total


def test_book_rejected_for_npd():
    f = Filing(2026, IP, regime="npd", income=100_000)
    try:
        build_book_tex(f, [], doc_date=date(2026, 6, 12))
    except ValueError:
        return
    raise AssertionError("expected no statutory book for НПД")


def test_tex_escape_specials():
    assert tk._tex_escape("A & B 50%") == r"A \& B 50\%"


def test_book_balanced_braces():
    f = Filing(2025, ORG, regime="usn", usn_object="dohody", income=3_000_000)
    tex = build_book_tex(f, [], doc_date=date(2025, 6, 12))
    assert tex.count("{") == tex.count("}")
    assert tex.count(r"\begin{document}") == 1 and tex.count(r"\end{document}") == 1


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:                               # noqa: BLE001
            failed += 1
            print(f"FAIL {t.__name__}: {exc!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
