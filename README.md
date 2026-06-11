# TaxKittie 🐯

Generate Russian **3-НДФЛ** (personal income-tax) **returns** for an **ИП on ОСНО** —
compute the tax, render a human-readable **RU/EN** summary, and emit the ФНС-format
**XML (КНД 1151020)** ready for upload to the Личный кабинет.

Companion to **CryptoKiddie** (which signs); TaxKittie *builds* the return.

*(The name **TaxKiddie** — matching CryptoKiddie's spelling — was also considered.)*

> Russian «декларация» is a **tax return** in English — "declaration" is a false friend.

## What it does

- **Tax engine** — income → professional deduction (20 % standard or itemized) →
  year-aware progressive НДФЛ → minus fixed страховые взносы; plus пени and
  late-filing fine (ст. 119 / 122) estimates.
- **Bilingual render** — the return as a readable RU + EN summary.
- **ФНС XML** — КНД 1151020 envelope for the Личный кабинет (sign with your КЭП).

## Status

Work in progress. The tax math and render are exact; the XML follows the documented
КНД 1151020 structure but **must be validated against the official year-specific ФНС
XSD before submission** — the format changes per year (2025 introduced the
five-bracket progressive scale).

## Usage

```bash
./taxkittie compute --year 2023 --income 1000000
./taxkittie xml     --year 2024 --income 0 --out return-2024.xml
```

(or `python3 taxkittie …`)

## Layout

Single executable — **`taxkittie`** — organised in sections: rates · model · tax · render · ФНС XML · CLI.

No third-party dependencies (Python ≥ 3.11, stdlib only).
