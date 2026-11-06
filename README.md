# MFT Futures Research

Minute-bar research on Chinese commodity and financial futures: data quality,
conditional return dependence, volatility forecasting and explicit fee/execution
accounting. The main experiment uses 54 products, training in 2016–2019 and
evaluation in 2020–18 October 2021.

Of 47 strategy variants, 28 have positive gross returns and none have positive net
returns under the specified exchange-fee scenario. This retrospective experiment
does not establish executable trading alpha.

## Notebook structure

| Notebook | Role |
|---|---|
| [01_data_quality_check.ipynb](01_data_quality_check.ipynb) | Audit 77 raw files, resolve duplicate conflicts and preserve minute boundaries |
| [02_research_statistics_features.ipynb](02_research_statistics_features.ipynb) | Segment-safe features, correlation estimands and uncertainty |
| [03_strategies_hypotheses.ipynb](03_strategies_hypotheses.ipynb) | Earlier 77-file hypotheses and walk-forward experiment; a separate historical study |
| [04_liquidity_activity.ipynb](04_liquidity_activity.ipynb) | Explicit retrospective selection of 54 products |
| [05_research_statistics_features_54.ipynb](05_research_statistics_features_54.ipynb) | Features, ACF, tails and descriptive volatility clustering |
| [06_strategies_hypotheses_54.ipynb](06_strategies_hypotheses_54.ipynb) | Frozen training thresholds and conditional future-price event studies |
| [07_forecasting_models_54.ipynb](07_forecasting_models_54.ipynb) | AR/MA/ARMA, GARCH/GJR/EGARCH and two-stage direction forecasts |
| [08_backtest_fees_risk_54.ipynb](08_backtest_fees_risk_54.ipynb) | Simulated execution, fee scenarios, sizing and portfolio risk |
| [09_final_audit_07_08.ipynb](09_final_audit_07_08.ipynb) | Independent forecast, normalization, sizing and full-ledger reconciliation |

For the current 54-product study execute **01 →02 →04 →05 →06 →07 →08 →09**.
Notebook 03 is a separate, more expensive legacy comparison, rather than an
execution dependency of 04–09. Its source definitions are referenced explicitly.
Notebooks retain executed outputs, English explanations and English chart labels.

## Environment and tests

Python 3.11 was used for validation. Scientific versions are pinned in
[requirements.txt](requirements.txt); execution/test dependencies are in
[requirements-validation.txt](requirements-validation.txt).

    python3.11 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt -r requirements-validation.txt
    .venv/bin/python tools/verify_publication.py
    .venv/bin/python -m pytest -q tests

GitHub Actions runs data-free mathematical, boundary, cache, notebook-schema and
publication-language checks. Full market-data calculations are a separate
integration run, with evidence in the audit reports.

## Raw data

Raw CSV inputs are unchanged from the existing
[research-snapshot-v1 release](https://github.com/Flidison/MFT_CMF_PROJ/releases/tag/research-snapshot-v1).
The two raw-data archives total approximately 817 MB compressed. Other research
archives belong to the earlier 01–03 snapshot; they are optional for historical
reproduction and are not current 54-product results.

The commands below use the GitHub CLI; browser downloads from the linked release
are an equivalent option. From a fresh checkout, verify before extraction:

    gh release download research-snapshot-v1 --repo Flidison/MFT_CMF_PROJ \
      --pattern 'raw-data-*.tar.gz' --dir .data-downloads
    .venv/bin/python tools/verify_data.py --archives .data-downloads --archives-only
    tar -xzf .data-downloads/raw-data-01.tar.gz -C .
    tar -xzf .data-downloads/raw-data-02.tar.gz -C .
    .venv/bin/python tools/verify_data.py

[data/raw_manifest.csv](data/raw_manifest.csv) pins every raw file's size and
SHA-256. The historical release manifest retains its archive checksums; it
describes that release, not the current source revision.

## Reproduction

Use an isolated checkout: notebooks save executed outputs in place and regenerate
artifacts. Each receives a new kernel; the runner records progress and source
hashes.

    .venv/bin/python tools/run_research.py \
      01_data_quality_check.ipynb \
      02_research_statistics_features.ipynb \
      04_liquidity_activity.ipynb \
      05_research_statistics_features_54.ipynb \
      06_strategies_hypotheses_54.ipynb \
      07_forecasting_models_54.ipynb \
      08_backtest_fees_risk_54.ipynb \
      09_final_audit_07_08.ipynb

Current CSV summaries, model JSONs, figures, fee inputs and compact historical
verification records are versioned. Large derived Parquet features, forecasts,
decisions and ledgers are regenerated and excluded from Git. The complete local
baseline remains preserved. Notebook 09 checks unchanged forecast columns using
published frozen fingerprints and historical common masks without the old
multi-gigabyte ledgers.

The bundled commission workbook is sufficient. If missing, explicitly set
MFT_FEE_WORKBOOK. MFT_FEE_ORIGINAL optionally enables comparison with an external
original; its absence is reported as unverified rather than silently certified.

## Audit and interpretation

- [Code audit and fixes](audit/2026-11-06/MFT_Code_Audit_and_Fixes.md)
- [Research validation](audit/2026-11-06/MFT_Research_Validation.md)
- [Nikolai handoff](audit/2026-11-06/MFT_Nikolai_Handoff.md)

Limitations remain retrospective universe/test selection, finite Monte Carlo
approximation, extreme EGARCH forecasts, minute-close fills, fractional lots,
incomplete historical trading-day/fee reconstruction, and omitted broker, spread,
impact and capacity costs. The baseline applies August 2026 exchange-fee
assumptions to 2020–2021; it is not a historical tariff reconstruction.

The 25-slide presentation has broader and partly different source coverage.
Several early-slide methods and universe counts cannot be reproduced from these
nine notebooks alone. The audit records those differences without changing the
research sample to match slides.


## Optional presentation diagnostics

The existing numerical diagnostics for the later presentation panels can be
recomputed after the core pipeline, using the same Python environment:

    .venv/bin/python artifacts/mft_lecturer_feedback/scripts/analyze_feedback.py
    .venv/bin/python artifacts/mft_lecturer_feedback/scripts/supplementary_checks.py
    .venv/bin/python artifacts/mft_lecturer_feedback/scripts/unusual_acf_validation.py

These scripts estimate no new trading strategy. Presentation-layout runtimes and
private deck-build directories are outside the notebook runtime. Original exchange
source documents retain their original language; research explanations are English.

For a new publication snapshot, stage the intended files, run
python tools/build_publication_manifest.py, then stage publication_manifest.csv
and commit. The manifest hashes staged Git blobs and excludes itself to avoid
recursive hashing. Verify a clean snapshot before regenerating its outputs.
