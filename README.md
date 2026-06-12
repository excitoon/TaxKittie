# TaxKittie 🐯

Compute Russian taxes for an **ИП** *or* an **ООО** across **every regime**, print a
bilingual **RU/EN** summary, and — for the regimes that file one — emit the ФНС
**XML** ready for upload to the Личный кабинет.

Companion to **CryptoKiddie** (which signs); TaxKittie *builds* the return.

*(The name **TaxKiddie** — matching CryptoKiddie's spelling — was also considered.)*

> Russian «декларация» is a **tax return** in English — "declaration" is a false friend.

## What it does

- **Entities** — `ИП` (sole proprietor) and `ООО` (organisation).
- **Regimes** — `ОСНО` (3-НДФЛ for an ИП · налог на прибыль + НДС for an ООО),
  `УСН` (доходы / доходы-расходы, with the 2025 НДС-over-60 млн rule and minimum
  tax), `ПСН`, `АУСН`, `НПД`, `ЕСХН`.
- **Insurance contributions** — ИП fixed «за себя» + 1 % over 300 000 ₽ (capped),
  and the УСН-доходы / ПСН reduction (100 % without employees, 50 % with).
- **Payroll** — employer страховые взносы (единый тариф, with the МСП reduced
  tariff) and 6-НДФЛ agent withholding on salaries.
- **Penalties** — пени (ст. 75) and the late-filing / non-payment fines (ст. 119 / 122).
- **ФНС XML** — КНД 1151020 (3-НДФЛ) and КНД 1152017 (УСН), windows-1251 encoded.

## Usage

```bash
# ИП on ОСНО — 3-НДФЛ
./taxkittie compute --regime osno --entity ip  --year 2023 --income 1000000

# ИП on УСН «доходы» (взносы reduce it automatically)
./taxkittie compute --regime usn  --object dohody --year 2025 --income 3000000

# ООО on ОСНО — налог на прибыль + НДС, two employees
./taxkittie compute --regime osno --entity org --year 2025 \
    --income 8000000 --expenses 5000000 --employee 100000 --employee 80000

# ИП patent
./taxkittie compute --regime psn  --year 2025 --potential-income 1000000

# emit ФНС XML (3-НДФЛ or УСН)
./taxkittie xml --regime usn --entity org --year 2025 --income 3000000 --out usn.xml
```

`--lang ru|en|both`, `--filing-date` / `--payment-date` (for penalties),
`--region-rate`, `--msp`, plus the identity flags (`--name --inn --kpp --ogrnip
--code --oktmo`). Run `./taxkittie compute -h` for the full list.
(or `python3 taxkittie …`)

## Status

Work in progress. The tax math, contributions, payroll and penalty estimates are
exact for the cases covered by the tests; a few **2026** parameters move (the
УСН-НДС 60 млн threshold, the единая предельная база, and the МСП reduced tariff
which became industry-gated for 2026) — these are flagged in the code. The XML
follows the documented КНД structure but **must be validated against the official
year-specific ФНС XSD before submission** — the format and `ВерсФорм` change per
year, and ПСН/АУСН/НПД file no return while налог-на-прибыль/ЕСХН XML is pending.

## Layout

Single executable — **`taxkittie`** — organised in sections: rates · model · tax ·
render · ФНС XML · CLI. The regime engine is a `regime → handler` table, so adding
a regime is one function plus its constants.

No third-party dependencies (Python ≥ 3.11, stdlib only). Tests: `python3 tests/test_tax.py`.
