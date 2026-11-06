# MFT Code Audit and Fixes

Audit started 6 November 2026; publication preparation followed the second review.
Scope: the owner's active 01–09 pipeline and its actual dependencies. External
teammate notebooks were not used as inputs to corrections.

## Version assessment and preservation

Before corrections, GitHub main, the local main commit and tag
research-snapshot-v1 all pointed to
83213aca2f4628bd81a18150fde4ab5a35f017de, dated 4 October 2026.
GitHub contained notebooks 01–03 and their historical snapshot. The complete
local 04–09 research was untracked and unpublished; README also had local changes.
The local working research, rather than the older published snapshot, was the
review target.

Corrections were made in a separate worktree on branch
codex/pre-handoff-validation. Before editing, the audit saved Git status/diffs,
SHA-256 records for 5,361 files, all nine notebooks, and copies of relevant
strategy/54-product outputs. A subsequent independent hash pass found **zero
changes in those 5,361 original-project files**.

The complete baseline and full historical ledgers remain local. Public Git
contains compact historical fit/CSV records, exact forecast-column fingerprints
and original common masks. These are derived from the preserved historical
inputs, never from current forecasts presented as historical data.

## Examined scope

All **191 code cells in nine notebooks** were inspected and executed in separate
kernels. The source review followed raw fields through cleaning, continuous
segments, features, tests, estimation, forecasts, decisions, fills, accounting
and portfolio metrics.

| Area | Examined files and data |
|---|---|
| Raw data and cleaning | All 77 CSVs; 01_data_quality_check.ipynb; data/quality manifests and all cleaning diagnostics |
| Features and legacy study | 02_research_statistics_features.ipynb; 03_strategies_hypotheses.ipynb; shared segment, correlation, ARMA, variance, logistic and walk-forward functions; stored fits/predictions |
| Current universe/statistics | 04_liquidity_activity.ipynb; 05_research_statistics_features_54.ipynb; universe JSON/CSV, 54 feature Parquets, moments, ACF, tails and coverage |
| Hypotheses and models | 06_strategies_hypotheses_54.ipynb; 07_forecasting_models_54.ipynb; thresholds, all 54 fit records, 53 forecast files, losses/calibration/cohorts |
| Execution and risk | 08_backtest_fees_risk_54.ipynb; workbook/source evidence; 54 decision files and 54 complete trade ledgers; daily/scenario portfolios |
| Independent final audit | 09_final_audit_07_08.ipynb; every script under artifacts/research_54/audit_code, including the historical cache-migration utility |
| Publication/reproduction | Requirements, Git/release manifests, runner, input verifier, tests and CI workflow |
| Presentation support | Local final_presentation_handoff and mft_lecturer_feedback numerical/plotting scripts; supplied 25-slide deck; supporting tables and provenance |

The audit modules are fee_audit.py, regression_tests.py, volatility_audit.py,
training_normalization_audit.py, risk_and_position_audit.py, execution_audit.py,
build_report.py, migrate_verified_cache_config.py and model_output_validation.py.
The one-time migration utility is historical, rather than a normal execution
step. Optional presentation builders are outside the public notebook runtime.

## Confirmed defects and fixes

There are **six root-cause groups**. Most are latent failures on invalid or
degenerate inputs; they were not observed as corrupted PnL in the supplied valid
market sample. No critical arithmetic defect was found in that sample's original
gross/net ledger. Cell numbers below are one-based.

| Issue | Severity | Location | Root cause | Fix | Verification | Status |
|---|---|---|---|---|---|---|
| F1. Successful volatility fit with zero likelihood observations | High if triggered; latent in supplied sample | 03 cell 66, wf_fit_volatility; 07 cell 7 and 08 cell 9, model_fit_volatility | A finite raw-row count could pass although every observation restarted a segment. The objective then had n=0, allowing a nominal optimizer success and undefined BIC. | Require an effective finite within-run lag pair before optimization; validate aligned arrays and finite positive scale in the current model fitter. | 1,002 finite observations in separate segments are rejected; GJR/EGARCH regression cases cover all three implementations. Existing successful fit records have positive effective n. | Fixed |
| F2. Invalid fee text silently parsed as a valid positive charge | Medium; latent | 08 cell 4, parse_fee | Unanchored numeric extraction ignored a minus sign, junk prefix or multiple numbers. | Full-string parsing; finite nonnegative amounts; explicit fee units and divisor rules. | Negative, prefixed and multi-number examples fail; fixed CNY and both explicit notional divisors retain their expected values. All real fee legs reconcile independently. | Fixed |
| F3. Nonphysical/nonfinite trade inputs silently produced invalid accounting | Medium; latent | 08 cell 17, account_trades | Zero/nonfinite prices or multipliers, negative charges and numerical overflow were not rejected. | Validate broadcast shapes, prices, multiplier, positions, charges, slippage and finite positive notional; reject nonfinite results. Preserve scalar and vector callers. | Twelve independent long/short, close-today/previous and slippage examples; scalar compatibility; invalid/overflow/underflow cases; complete real-ledger reconciliation. | Fixed |
| F4. Invalid risk inputs and daily ledgers accepted | Medium; latent | 08 cell 25, empirical_es and performance | Empty/nonfinite loss samples or invalid confidence levels were accepted; pandas could skip NaNs in inconsistent daily PnL. | Validate nonempty finite samples and levels in [0,1); require complete finite daily inputs and gross−costs=net before metrics. | Known fractional-tail ES examples; invalid inputs; scalar capital-account reconstruction of compounding, Sharpe and drawdown. | Fixed |
| F5. Unsupported original-workbook comparison claim | Low; active when external original is absent/different | artifacts/research_54/audit_code/fee_audit.py, original_copy_evidence/main; 08 cell 2 input setup | JSON allowed an unavailable original, but prose always claimed byte-for-byte agreement. A personal Downloads path also obscured reproduction. | Make the statement conditional on the actual comparison; use the bundled workbook, with explicit optional environment paths. | Absent, equal and different source-copy cases; source XML/fee coefficients independently reconciled. | Fixed |
| F6. Fresh/warm cache exported different parameter representations | Medium; active in fresh estimation | 07 cell 19, result collection before DataFrame/CSV export | Fresh fits retained NumPy arrays/tuples while loaded JSON held lists. Fresh CSV used rounded, non-JSON NumPy array text; warm CSV had full-precision lists. | Canonicalize result containers through the existing JSON-safe representation before collection in either path. | Execute the actual collection cell twice on 54 synthetic records; require a genuine warm-cache hit, identical CSV bytes and exact round-trip coefficients. Fresh full-market and cached runs were also exercised. | Fixed |

These changes do not alter hypotheses, training/test dates, model orders,
penalties, persistence constraints, fee scenario amounts, universe membership or
execution rules to improve performance.

## Independent mathematics and financial checks

The tests and independent audit do not use the producing accounting helper to
construct expected PnL. References include:

- Timestamp/contract-based log returns and explicit rolling sample standard deviations.
- Direct lag-pair Pearson correlations; a dense Bartlett-weight matrix for HAC;
  the influence-score derivative; independent excess-kurtosis reconciliation.
- Scalar ARMA innovations/reset rules, scalar GARCH/GJR/EGARCH recursions and
  finite-difference likelihood gradients.
- Explicit future-return windows for horizons 1/5/30 and delays 0/1.
- EGARCH future offsets computed as a matrix convolution, independently of the
  production recursive factor generator.
- Per-leg fees and signed quantity arithmetic, adverse fills, daily capital,
  compounding, initial-equity drawdown, historical VaR and fractional-mass ES.

Quantity/capital is position/(signal price × multiplier). Gross is quantity ×
multiplier × (exit close−entry close). Each exchange leg is absolute quantity ×
(fixed CNY/lot + fill price × multiplier × decimal rate). Daily portfolios retain
54 equal capital sleeves, including unavailable/cash sleeves.

The independent saved-ledger pass covered **34,806,565 rows**, including repeated
strategy/cohort experiments. Maximum daily reconstruction differences were
0 for gross and turnover and **3.47×10⁻18** for costs/net. There were no overlapping
entries, wrong earliest eligible exits, contract-run crossings or invalid saved
fill prices in the checked ledgers.

## Regression and numerical impact

The final test suite contains **103 added cases**. Against the preserved
pre-correction notebook source, **29 fail and 74 pass**; against the corrected
source, **103 pass**. The separate existing 09 regression module has 14 checks,
including a deliberately passing demonstration of the calendar-date limitation.
Full execution also runs seven independent audit modules.

The original Monte Carlo convention is retained. A candidate common-prefix
change was rejected in the second review: reshaping Gaussian draws for a
different requested horizon is a legitimate finite-simulation convention, not
proof of estimator bias. The final tests instead reproduce the original
fixed-horizon simulation directly. **No forecast-column change allowance is
permitted by the final baseline validator.**

The intended numerical outcome is preservation of all valid-input forecasts,
fitted coefficients, trade ledgers and portfolio results. Changes in language,
validation messages, source/cache fingerprints and full-precision container
serialization are identified separately in the final verification receipt.
No numeric research result was manually edited.

Representative unchanged current result: S8 available-cohort net return
**−0.2772854678172591**, Sharpe **−19.591127911262287**, **792,764 trades**.
The primary S0–S9 set has 9/10 gross-positive and 0/10 net-positive variants;
all 47 have 28 gross-positive and zero net-positive variants.

## Second review and unresolved matters

The second review checked the actual corrected recursions, fresh/cache execution,
invalid-input paths, full trade chronology, numerical regression and source/output
lineage. It caught and corrected an interim scalar-input compatibility regression.
It also rejected the unnecessary Monte Carlo convention change.

The following are limitations or assumptions, not repaired implementation errors:

- Retrospective 54-product selection and repeated inspection of 2020–2021.
- GARCH/GJR persistence ceiling below 0.999; a deliberate model constraint.
- Extreme but finite EGARCH forecasts and finite Monte Carlo approximation.
- Different 53/54/46-product evaluation cohorts and different target windows.
- August 2026 fee scenarios applied to 2020–2021, unresolved I/AG/SC scope.
- Calendar dates do not certify official historical trading-day labels.
- Fractional lots, close fills and absent spread, broker, impact and capacity modelling.
- The broader presentation cannot be fully sourced from the active nine-notebook chain.

See the research validation and handoff documents for the final readiness verdict
and reproduction limits.
