# MFT Nikolai Handoff

## Authoritative version

Use the publication commit containing this document and verify its Git SHA.
The baseline commit 83213aca2f4628bd81a18150fde4ab5a35f017de is the older
4 October 2026 snapshot, not the complete current research.

The reviewed local worktree is MFT_CMF_PROJ_pre_handoff, branch
codex/pre-handoff-validation. The original MFT_CMF_PROJ working directory and raw
research state remain preserved. Source/output checksums identify the reviewed
files; publication_manifest.csv inventories the Git payload and data/raw_manifest.csv
pins the unchanged raw inputs.

All nine notebook explanations, comments and displayed outputs are English.
The scientific fixes are limited to demonstrated correctness/reproduction failures;
the original model specifications and fixed-horizon Monte Carlo convention remain.

## Execution order and dependencies

Current 54-product pipeline:

1. 01_data_quality_check.ipynb — clean and audit 77 raw source files.
2. 02_research_statistics_features.ipynb — segment-safe features and original statistics.
3. 04_liquidity_activity.ipynb — frozen retrospective 54-product universe.
4. 05_research_statistics_features_54.ipynb — current features and descriptive statistics.
5. 06_strategies_hypotheses_54.ipynb — training-calibrated event studies.
6. 07_forecasting_models_54.ipynb — mean/variance/direction estimation and forecasts.
7. 08_backtest_fees_risk_54.ipynb — explicit execution, fees, sizing and accounting.
8. 09_final_audit_07_08.ipynb — independent full-result reconciliation.

03_strategies_hypotheses.ipynb is the earlier 77-product experiment. It can be
executed after 02, but is not an execution prerequisite of the current 54-product
study. Its source definitions are explicitly referenced. Its expensive historical
walk-forward predictions were reused only after checking mathematical equivalence,
all 77 prediction hashes and 12,794 positive-observation fit records. It was then
executed in a new kernel. This is not a fresh re-estimation of every legacy fit.

Use Python 3.11 and the exact requirements.txt/requirements-validation.txt.
Core dependencies are NumPy, pandas, SciPy, PyArrow, Numba, statsmodels, Matplotlib,
IPython and threadpoolctl. Models are implemented locally; the arch documentation
is a reference, not a required modelling package. Optional presentation diagnostics
use the same scientific stack; presentation-layout tooling is not needed.

## Reproduction

From an isolated checkout:

    python3.11 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt -r requirements-validation.txt
    .venv/bin/python -m pytest -q tests

Follow README's two-archive download/checksum/extraction instructions for all
77 raw CSVs. Then execute the documented notebook sequence with tools/run_research.py.
Every notebook receives a fresh kernel and saves outputs in place. The current
CSV/JSON results and English figures are versioned; heavy feature/forecast/
decision/trade Parquets are recreated rather than stored in Git.

The bundled commission_schedule.xlsx is the baseline fee input. Optional
MFT_FEE_WORKBOOK supplies a missing workbook; MFT_FEE_ORIGINAL enables comparison
with an external original. Missing originals are explicitly unverified.

Notebook 09 needs the versioned compact historical baseline: fitted parameters,
CSV tables, exact forecast-column fingerprints and common-cohort masks. It can
perform strict comparisons without the complete private historical ledgers.
The full preserved snapshot remains available locally for deeper history review.

## Validation evidence

The final source passes **103 tests**. The preserved pre-correction notebook
source fails 29 of those cases and passes 74. Tests include independent
mathematical examples, invalid inputs, actual fresh/warm collection-cell execution,
strict compact-baseline corruption detection and English/schema checks.

The complete local integration run executed nine notebooks and 191 code cells in
separate kernels. Notebook 09 additionally runs seven audit modules and 14 existing
regression checks. Independent calculations covered 34,806,565 saved ledger rows;
daily net reconstruction differs by at most 3.47×10⁻18. Public CI runs the data-free
suite; it does not claim to re-estimate the entire market-data pipeline.

Review the six issue groups in MFT_Code_Audit_and_Fixes.md and the machine-readable
verification summary. Important original results are unchanged: 28/47 gross-positive
and 0/47 net-positive variants; S0–S9 have 9/10 gross-positive and 0/10 net-positive.
Sample S8 available net return is −27.7285468% on 792,764 trades.

## Assumptions to keep in view

- Universe membership and research choices use previously inspected 2016–2021
  history; the chronological test is not pristine external evidence.
- Standalone 07 has 53 eligible products, all-seven direction has 46, and the
  disclosed 08 SA extension gives 54. Compare matching cohorts and targets.
- Standalone h5 is t+1…t+5; planned delayed holding risk is the variance sum
  t+2…t+6. Finite Monte Carlo paths can differ across requested horizons.
  Additive variance sizing assumes zero future cross-covariances in its working
  volatility model; it is not a jointly estimated ARMA–GARCH holding-PnL variance.
- Sizing uses signal price, fractional contracts and normalized capital.
  Every unavailable sleeve retains cash. Close fills and positive minute volume
  do not establish live execution or margin feasibility.
- The baseline applies August 2026 exchange-fee assumptions to 2020–2021,
  excluding broker/spread/impact costs. I/AG/SC scope remains unresolved.
- Same calendar date does not certify an official exchange trading day.
  Delayed exits are retained and unresolved entered positions stop PnL.
- Finite EGARCH forecasts can be extreme. Suspect source prints are retained
  pending external market confirmation.
- The broader 25-slide deck contains different universe counts and methods not
  fully sourced by this active pipeline. The research-validation document lists
  the affected claims.


## Readiness verdict

**READY WITH CAVEATS.** The verified active calculations and saved outputs are
current and reproducible in the tested Python 3.11.7 macOS environment. Six
confirmed correctness/reproduction defect groups are fixed; no known material
implementation error remains within the verified scope. All forecasts, fitted
coefficients and financial results preserve the original valid-input experiment.

The caveats concern research-selection bias, simulation/execution/fee/calendar
assumptions, unverified broader presentation sources and reuse of verified
legacy walk-forward fits. Public CI checks the data-free suite on Linux; a full
market-data re-estimation on a different OS/BLAS backend is not certified as
bit-identical to the archived fit snapshot. These limits should accompany the
code when it is reviewed as quantitative research.
