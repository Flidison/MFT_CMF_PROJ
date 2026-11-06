# Final audit of Notebooks 07–08

**Historical backtest under August 2026 exchange-fee assumptions.**

## Executive summary

Computations are reproducible within the documented bar-close and fee scenarios. This is **not certification of real-world tradability, a pristine holdout, or the historical exchange calendar**. Notebook 08 was corrected and fully rerun; Notebook 07 was freshly estimated under the unchanged training specification during the pre-handoff audit. Every fitted coefficient matches the preserved snapshot exactly. Every forecast column must match the preserved baseline; a separate matrix-convolution reference checks the original fixed-horizon EGARCH simulation. No tuning used test performance. No critical arithmetic defect was found in the supplied gross/net ledger.

- All 54 instrument ledgers, **34,806,565 strategy/cohort trade rows**, were independently reconciled against source prices, quantities, commission formulas and daily/equity aggregation. These rows repeat market events across strategies; they are not independent observations.
- **28/47** available-universe strategies have positive compounded gross returns; **0/47** have positive net returns after the scenario exchange fees. S0–S9: **9/10 gross-positive, 0/10 net-positive**; corrected common cohort: **9/10 and 0/10**.
- Correcting the S0–S9 common mask adds **70,314 forecast-available origins**, before execution conditions. Originally 70,051 of the excluded origins satisfied clock/positive-volume gates. All 47 available-universe results remain unchanged within 1e-12; common-cohort changes are shown below.
- **5,974 unique delayed-exit events**; maximum holding 30 minutes. One event crosses the observed 10:15–10:30 session break (RR2108,2021-05-31,10:01→10:31), repeated across 8 available strategy variants. No actual trade crosses a contract run or calendar date; no position overlap or unresolved entry remains.
- Volatility is predictable, but superiority over EWMA depends on horizon/cohort/year. A modest combined-period improvement at the actual planned Notebook 08 window does not establish stable tradable alpha.

## Findings, severity and disposition

| Severity | Type | Finding | Action/status |
| --- | --- | --- | --- |
| Medium | Confirmed code defect |08 S0–S9 common mask required unused asymmetric-logit and breakout predictors. |Fixed in `PRIMARY_COMMON_FIELDS` / `primary_common_mask`; rerun all 08 outputs; regression covers unused/required NaNs. |
| Medium | Confirmed validation defect |08 checked forecast bytes but did not bind fit-cache fingerprint to 07 config and feature record. A stale fit with a self-consistent forecast hash could pass. |Added source-function hash, manifest/universe/split and fit-fingerprint guards; changed-record regression passes. Actual pre-audit caches were consistent, so this fix changes no signals. |
| Low | Source-label defect |Excel calls SA soda ash/caustic soda and NR RSS3/20#. |Canonical audit labels SA=soda ash and NR=TSR20; raw workbook text retained; product codes/costs unchanged. |
| Medium | Confirmed cache-key defect |07 fingerprint omitted global window/model settings, so changing those could reuse stale predictions. |Added runtime constants to config, migrated only independently verified current caches, and reran 07 with cached forecasts. Regression confirms window changes invalidate the key. Fitted coefficients and forecasts remain unchanged; the later pre-handoff audit also verifies full-precision fresh/cache CSV exports. |
| High | Model diagnostic / unresolved limitation |EGARCH has 6 finite planned-hold variance forecasts above1 across 4 products; the maximum is 2.71256e+06. |Independent reconstruction agrees. Convergence/nonfinite checks alone do not establish stability. Original forecasts and sizing retained; no test-selected clipping/refit. See `audit_egarch_forecast_extrema.csv`. |
| High | Fee-source uncertainty |‰ contradicts Notes; I divisor unverified; AG near/far and SC front-month applicability not reconstructed. |Retained explicit scenarios, added isolated I/1000 sensitivity. No selection by profitability and no invented SC fallback. |
| High | Research-design limitation |Universe uses 2016–2021 liquidity history; hypotheses/test were already inspected; session buffer introduced after examining exit failures. |Results are descriptive; 2020–2021 is not a pristine holdout. |
| High | Execution/calendar limitation |Close t+1 is a bar-fill assumption; calendar date is not an exchange trading-day label. |Actual crossings audited, future failure behavior tested; official historical calendar/order-book execution remains unverified. |
| Medium | Comparability limitation |07 standalone eligibility 53; 08 adds SA using 19 train dates. Composite models remain 46. |Explicit 53/54 cohorts and cash sleeves retained; no missing forecasts replaced by zero. |

No strategy, hypothesis, holding horizon, model coefficient, fee base value or test-selected threshold was optimized during this audit.

## Execution and trading calendar

Signal features contain observations through close t. Contract quantity is fixed from signal price before entry. The simulator evaluates entry at exact t+1; missing minute, invalid OHLC or nonpositive/unknown volume cancels then. Prices/volume at later exits are not used to admit entry. Scheduled exit is t+6, five minutes after entry. If untradeable, the first valid positive-volume bar in the same contiguous contract run and calendar date closes the position. Other origins are blocked until close; unresolved entered positions retain their entry and prevent publication of aggregate PnL.

An order submitted after t cannot guarantee the future close t+1 price. Observing a positive bar volume and valid close only supports the specified bar simulation; it does not prove order acceptance, available depth, queue position or execution price. No intrabar fill path is reconstructed.

Independent full-ledger checks: exact one-minute entry lag; hold≥5; all fill bars valid with positive finite volume; earliest eligible exit; same contiguous delivery contract; no overlapping positions. Contract expiration legality is not independently certified by an official contract calendar. Missing-minute entries are tested synthetically; none appear in the actual counted execution cancellations. Existing cancellation totals and no-order totals are preserved in `execution_diagnostics.csv` (status0 includes unavailable/cash/zero signals).

The observed-session proxy increments at source gaps>10 minutes or contract-run changes; it is **not** a trading-day calendar. The sole observed session crossing matches DCE's documented intraday break ([official guide, printed p9](https://www.dce.com.cn/dalianshangpin/resource/cms/2017/04/%E6%9C%9F%E8%B4%A7%E5%85%AC%E5%8F%B8%E8%B1%86%E7%B2%95%E6%9C%9F%E6%9D%83%E4%B8%9A%E5%8A%A1%E6%8C%87%E5%8D%97%281%29.pdf)). Calendar-date logic can theoretically allow day→night exits on different exchange trading days; a dedicated test demonstrates this limitation. No such actual day→night exit was found. Short trades within the observed sessions use Close Today; Close Previous is independently tested but is not used in this no-overnight experiment. Night-session dates, holidays and midnight are not fully certified without an official dated calendar.

### Holding times and delayed exits

| strategy | cohort | trades | delayed exits | mean holding minutes | median holding minutes | p95 holding minutes | p99 holding minutes | max holding minutes | over 10 minutes | over 15 minutes | over 30 minutes | observed session gap crossings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S0 | available | 954278 | 4547 | 5.00679 | 5 | 5 | 5 | 20 | 50 | 4 | 0 | 0 |
| S0 | common | 703400 | 1844 | 5.00341 | 5 | 5 | 5 | 19 | 8 | 1 | 0 | 0 |
| S1 | available | 1075195 | 5974 | 5.00811 | 5 | 5 | 5 | 30 | 72 | 9 | 0 | 1 |
| S1 | common | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S2 | available | 1075195 | 5974 | 5.00811 | 5 | 5 | 5 | 30 | 72 | 9 | 0 | 1 |
| S2 | common | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S3 | available | 1075195 | 5974 | 5.00811 | 5 | 5 | 5 | 30 | 72 | 9 | 0 | 1 |
| S3 | common | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S4 | available | 933386 | 2538 | 5.00361 | 5 | 5 | 5 | 19 | 16 | 1 | 0 | 0 |
| S4 | common | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S5 | available | 933386 | 2538 | 5.00361 | 5 | 5 | 5 | 19 | 16 | 1 | 0 | 0 |
| S5 | common | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S6 | available | 933386 | 2538 | 5.00361 | 5 | 5 | 5 | 19 | 16 | 1 | 0 | 0 |
| S6 | common | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S7 | available | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S7 | common | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S8 | available | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S8 | common | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S9 | available | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |
| S9 | common | 792764 | 2269 | 5.00375 | 5 | 5 | 5 | 19 | 10 | 1 | 0 | 0 |

For the representative full-coverage S1 timing schedule, delayed positions have observed durations up to 30 minutes. Some other variants share the exact same events; do not sum across strategies as distinct market incidents. The full file-level table includes >5,>10,>15,>30 minute counts, cancellations, invalid/missing deadline bars and unresolved entries.

Delayed-trade contributions below use the same start-of-day **net** capital and 1/54 instrument allocation. They include both PnL and fees, rather than dropping delayed trades:

| Strategy | delayed exits | delayed gross pnl on net capital | delayed exchange fees on net capital | delayed net pnl on net capital |
| --- | --- | --- | --- | --- |
| S0 | 4547 | -0.00307427 | 0.0011334 | -0.00420767 |
| S1 | 5974 | 0.0016617 | 0.00216382 | -0.000502128 |
| S2 | 5974 | 0.00153991 | 0.00206796 | -0.000528049 |
| S3 | 5974 | 0.00166248 | 0.00216367 | -0.000501186 |
| S4 | 2538 | 0.000765435 | 0.000786651 | -2.12153e-05 |
| S5 | 2538 | 0.000654532 | 0.000768619 | -0.000114088 |
| S6 | 2538 | 0.000785962 | 0.000784041 | 1.92153e-06 |
| S7 | 2269 | 0.000425604 | 0.000309199 | 0.000116405 |
| S8 | 2269 | 0.000385122 | 0.000295566 | 8.95555e-05 |
| S9 | 2269 | 0.000425819 | 0.000309227 | 0.000116592 |

The CSV also records gross PnL minus a mark at the scheduled exit where that close exists. A zero-volume or invalid-bar mark is **not a tradable counterfactual**; it cannot justify replacing the executed exit or claiming a causal benefit from delay.

Optional explicit delay-monitor configuration: `max_exit_delay_minutes=5`, meaning alert after 10 minutes total holding, with `breach_action='flag_and_retain_observed_exit'`. The audit compares0,5,10,25 minutes of extra delay below for S1. This changes flags only; observed exits and PnL remain intact. A hard liquidation cap needs a defensible executable fallback price and cannot be implemented by deleting breached positions. No hard cap has been silently introduced.

| max exit delay minutes | breach positions | breach gross sum | breach net sum |
| --- | --- | --- | --- |
| 0 | 5974 | 0.169532 | -0.124948 |
| 5 | 72 | 0.0087476 | 0.00381001 |
| 10 | 9 | 0.00188278 | 0.00115417 |
| 25 | 0 | 0 | 0 |

## Independent PnL, fees and aggregation

For signed normalized position w and price multiplier M: q=w/(signal_price×M); notional_entry=abs(q)×M×entry_fill, similarly exit. Gross=q×M×(exit_close−entry_close). Each exchange leg=abs(q)×fixed_CNY_per_lot+notional×decimal_ratio. Long/short pay fees on absolute quantity. Adverse slippage changes both fills; execution cost=abs(q)×M×(entry_close+exit_close)×bp/10000. Broker cost=2×abs(q)×broker_CNY_per_side.

**Net PnL=Gross PnL−Exchange Fees−Broker Fees−Execution Costs**, with no second subtraction. Independent tests cover fixed, ratio, combined synthetic fees, long/short, Close Today/Previous, and 0/.5/1 bp. Real sampled trades and all intermediate notionals are in `audit_trade_reconciliation_sample.csv`; all actual base rows and all five alternative scenario daily ledgers were independently checked.

Maximum absolute discrepancies: trade PnL/cost fields **1.73e-18**; portfolio daily net **3.47e-18**; net equity **1.11e-16**; net-capital PnL↔equity identity **3.11e-15**. The maximum across all checked ledger/performance fields, including turnover, is **5.68e-14**. Detailed errors are in `audit_execution_summary.json`.

Instrument/day sums divide by a fixed54 to obtain portfolio/day returns, retaining unavailable sleeves as cash. Capital is reset/reallocated daily and compounds across 657 calendar days; Sharpe annualization uses 365.25 and sample daily standard deviation. VaR95 and the exact worst5% empirical-mass ES95 were independently recomputed. Gross and net equity compound separately: gross return minus net return is **not** the accounting fee sum. The following gross/cost/net contributions share one net-capital path and do reconcile:

| Strategy | gross pnl on net capital | exchange fees on net capital | net pnl on net capital | Net + 0.5 bp/side | Net + 1 bp/side | Net: I divisor 1000 only |
| --- | --- | --- | --- | --- | --- | --- |
| S0 | -11.5001% | 85.2626% | -96.7627% | -99.4568% | -99.9095% | -97.4406% |
| S1 | 1.8389% | 92.2971% | -90.4582% | -98.0915% | -99.6206% | -91.3077% |
| S2 | 1.6943% | 91.2324% | -89.5380% | -97.7854% | -99.5338% | -90.4307% |
| S3 | 1.8337% | 92.2995% | -90.4658% | -98.0939% | -99.6213% | -91.3147% |
| S4 | 4.3980% | 92.3229% | -87.9249% | -97.1145% | -99.3138% | -88.9994% |
| S5 | 3.6986% | 90.8153% | -87.1167% | -96.7581% | -99.1878% | -88.2155% |
| S6 | 3.7618% | 91.8739% | -88.1121% | -97.1605% | -99.3250% | -89.1701% |
| S7 | 0.2244% | 29.4750% | -29.2506% | -43.8650% | -55.4662% | -30.1578% |
| S8 | 0.2685% | 27.9970% | -27.7285% | -41.9633% | -53.3997% | -28.6046% |
| S9 | 0.2119% | 29.4878% | -29.2760% | -43.9025% | -55.5097% | -30.1839% |

### Fee authority

All 54 exact code/exchange matches,37fixed and 17ratio; all three legs independently parsed from Excel. Workbook original/copy SHA256 agrees. Maximum coefficient error=5.42e-20. Test vendor-implied multiplier medians agree within 0.5% for 54/54; worst deviation=0.060827%. T/TF10000 is also supported by the official CFFEX contract table.

Formula verification is not tariff certification. `fee_audit.csv` retains raw text, decimal units, multipliers, canonical product descriptions, URLs/effective dates, evidence confidence,54 base rows and 36 scenario rows. The [03Aug2026 SHFE snapshot](https://www.shfe.com.cn/data/busiparamdata/future/Settlement20260803.dat) differs from multiple Excel entries (including CU close-today, SP/FU, NR fee type); these were not replaced with more attractive rates. I remains an assumption; AG near-all is an Excel what-if, not a verified historical near-month mapping; SC non-front rate is unknown and has no fabricated scenario. Full evidence is in `audit_evidence/fee_findings.md`.

Base: exchange fees included; broker markup0; slippage0; spread unmodeled. Added0.5/1 bp per side is a sensitivity, **not full transaction costs**.

| scenario | strategies | positive net |
| --- | --- | --- |
| AG_near_month_all | 47 | 0 |
| all_ratio_literal_1000 | 47 | 0 |
| all_ratio_notes_10000 | 47 | 0 |
| exchange_only | 47 | 0 |
| slippage_0.5bp_side | 47 | 0 |
| slippage_1bp_side | 47 | 0 |

## Notebook 07↔08 consistency and coverage

Current07 function hash matches its manifest; all 54 feature hashes and fit fingerprints match; 53 forecast caches match their hashes, IDs and timestamps. All seven corresponding direction series agree07→08 on the53 forecast files. SA is a disclosed08-only standalone extension, independently checked for risk and training-only data. It is not relabelled as a07 forecast.

ARMA/standalone risk parameters use2016–2019. Composite volatility feature fits use2016–2018; direction/logistic calibration uses settled2019 labels. Independent reconstruction uses no test rows and no optimizer: **230 fit checks**, **1288 logistic feature checks**, maximum center/scale discrepancies **2.66e-15/4.44e-16**. D2 standardizes r[t] with sigma[t|t−1], available before r[t]; prediction at close t can then use the observed r[t]. Risk sizing sums conditional variances for t+2…t+6. All 162 instrument/model risk series and 34,806,565 executed position sizes are independently checked. Position sizes match exactly (max error 0); maximum absolute risk-forecast discrepancy is 4.66e-10, with every comparison passing relative tolerance1e-11 and absolute tolerance1e-18. The largest absolute discrepancy occurs for an extreme NI EGARCH variance, not for PnL. EGARCH retains its original requested-horizon random-stream convention:08 simulates six steps and 07 standalone forecasts simulate30. Different finite Monte Carlo paths across those requests are valid; the independent reference reconstructs the corresponding fixed-horizon experiment. The independent audit regenerates the actual08 six-step paths; it does not substitute07 mean variance into holding-risk sizing. Logistic target is log(C[t+6]/C[t+1]); training labels must settle before 2020. Future target masks are used only in forecast scoring, never for trading admission.

The original 08 common mask over-restricted S0–S9 by unused auxiliary predictors; the corrected cohort requires exactly the six direction series and three risk forecasts they use. All strategies keep54 capital sleeves even when only 46 models are available. Different trade counts within common availability are legitimate zero/no-order signals, not different future-target filters.

Missing-model reasons:

| file | train dates | status | inner status | reason |
| --- | --- | --- | --- | --- |
| EG9999.XDCE.csv | 259 | eligible | insufficient_pre2019_history | Insufficient pre-2019 training history for composite models. |
| SA9999.XZCE.csv | 19 | insufficient_train_dates_returns_or_variance | — | 07 minimum 20 train dates; SA has 19. 08 extension is separately fitted. |
| EB9999.XDCE.csv | 64 | eligible | insufficient_pre2019_history | Insufficient pre-2019 training history for composite models. |
| CJ9999.XZCE.csv | 166 | eligible | insufficient_pre2019_history | Insufficient pre-2019 training history for composite models. |
| SS9999.XSGE.csv | 79 | eligible | insufficient_pre2019_history | Insufficient pre-2019 training history for composite models. |
| UR9999.XZCE.csv | 97 | eligible | insufficient_pre2019_history | Insufficient pre-2019 training history for composite models. |
| NR9999.XINE.csv | 97 | eligible | insufficient_pre2019_history | Insufficient pre-2019 training history for composite models. |
| RR9999.XDCE.csv | 93 | eligible | insufficient_pre2019_history | Insufficient pre-2019 training history for composite models. |

Available and common results (returns compounded, costs separately decomposed above):

| Strategy | cohort | Gross return | Net after exchange fees | sharpe | maximum drawdown | trades | mean holding minutes | available instruments | available observations | eligible signal observations |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S0 | available | -25.61% | -96.76% | -23.0477 | 96.76% | 954278 | 5.00679 | 54 | 1267157 | 1081408 |
| S1 | available | 2.19% | -90.46% | -22.9654 | 90.46% | 1075195 | 5.00811 | 54 | 1267825 | 1081668 |
| S2 | available | 1.99% | -89.54% | -23.3757 | 89.54% | 1075195 | 5.00811 | 54 | 1267825 | 1081668 |
| S3 | available | 2.15% | -90.47% | -22.9653 | 90.47% | 1075195 | 5.00811 | 54 | 1267825 | 1081668 |
| S4 | available | 11.54% | -87.92% | -23.0767 | 87.92% | 933386 | 5.00361 | 46 | 1089973 | 935979 |
| S5 | available | 8.60% | -87.12% | -23.6639 | 87.12% | 933386 | 5.00361 | 46 | 1089973 | 935979 |
| S6 | available | 9.85% | -88.11% | -23.076 | 88.11% | 933386 | 5.00361 | 46 | 1089973 | 935979 |
| S7 | available | 0.14% | -29.25% | -19.0431 | 29.25% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S8 | available | 0.21% | -27.73% | -19.5911 | 27.73% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S9 | available | 0.12% | -29.28% | -19.045 | 29.28% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S0 | common | -15.70% | -92.67% | -22.8383 | 92.67% | 703400 | 5.00341 | 46 | 947951 | 795105 |
| S1 | common | 0.27% | -85.43% | -22.7756 | 85.43% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S2 | common | 0.15% | -84.03% | -23.2613 | 84.03% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S3 | common | 0.23% | -85.44% | -22.7754 | 85.44% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S4 | common | 9.86% | -84.03% | -23.0396 | 84.03% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S5 | common | 7.66% | -82.83% | -23.6093 | 82.83% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S6 | common | 8.28% | -84.26% | -23.0016 | 84.26% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S7 | common | 0.14% | -29.25% | -19.0431 | 29.25% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S8 | common | 0.21% | -27.73% | -19.5911 | 27.73% | 792764 | 5.00375 | 46 | 947951 | 795105 |
| S9 | common | 0.12% | -29.28% | -19.045 | 29.28% | 792764 | 5.00375 | 46 | 947951 | 795105 |

## Volatility and return-property findings

Independent source-return recomputation on 54 products, test2020–18Oct2021: median ACF(r,1)=-0.08113, ACF(abs(r),1)=0.23141, excess kurtosis=12.0623. All 54/54 have positive excess kurtosis and a greater3-sigma tail probability than Gaussian. These are descriptive minute-return properties; zero-volume bars and microstructure effects remain in the defined all-bars sample. Lags1/5/10/30 and train/test evidence are saved in `audit_code/return_properties_independent.csv`.

QLIKE is log(max(forecast,floor))+realized_variance/max(forecast,floor); floor=1e-8×each instrument's **training variance**. Negative QLIKE levels are possible under this constant-omitting definition; paired differences are meaningful. No base forecast hits this floor in the reported comparisons. Returns are demeaned by training mean for the realized-variance target. Correlations below are medians of instrument correlations between forecast and realized **volatility**, not pooled correlations; QLIKE means give equal weight to products.

07's original h5 predicts t+1…t+5 and compares all 6 models on a common mask including Trailing30. At that original scope, median GARCH/GJR correlations are 0.558330/0.557944 versus EWMA 0.567501; mean deltaQLIKE is +0.010165/+0.010185 (worse). The independent audit reproduces those metrics (maximum error 1.78e-15). Removing the unrelated Trailing30 burn-in changes the sample; both explicitly labelled cohorts remain available. No more favorable cohort replaces the original result silently.

To match08's **planned** five-minute hold, the supplementary comparison below uses t+2…t+6, includes the separately identified SA extension, and has 54 products/1,184,638 matched origins. It does not score the variable horizon of positions whose exits were delayed beyond five minutes.

| period | model | instruments | n | volatility correlation | qlike delta ewma | median qlike delta ewma | better than ewma instruments |
| --- | --- | --- | --- | --- | --- | --- | --- |
| test | EWMA | 54 | 1184638 | 0.544994 | 0 | 0 | 0 |
| test | V1_GARCH | 54 | 1184638 | 0.545201 | -0.00185757 | -0.000858037 | 30 |
| test | V3_GJR_GARCH | 54 | 1184638 | 0.545292 | -0.00197745 | -0.00100157 | 31 |
| 2020 | EWMA | 54 | 640342 | 0.508214 | 0 | 0 | 0 |
| 2020 | V1_GARCH | 54 | 640342 | 0.513319 | -0.00388942 | -0.00141226 | 31 |
| 2020 | V3_GJR_GARCH | 54 | 640342 | 0.512135 | -0.00410838 | -0.00125597 | 32 |
| 2021 | EWMA | 54 | 544296 | 0.511777 | 0 | 0 | 0 |
| 2021 | V1_GARCH | 54 | 544296 | 0.508712 | 0.000344923 | 0.000476663 | 25 |
| 2021 | V3_GJR_GARCH | 54 | 544296 | 0.509397 | 0.00033296 | 0.000413372 | 25 |

GARCH/GJR gains are small and fail to persist across 2020/2021; positive volatility correlation is not evidence of a profitable direction strategy. On original Notebook 07 h5 common-all6, GJR improves QLIKE over GARCH for 28/53 products; on GARCH/GJR/EWMA-only common observations, 31/53. Selection of a scoring cohort changes that count, so it must be named.

All 53 full-train fits succeed for each volatility family, with boundary flags: GARCH 2, GJR 2, EGARCH 1. Inner 46 fits have 5, 5, 1 respectively. EGARCH filter/forecast guard hits are retained in diagnostics, with zero nonfinite forecast counts. GJR negative-shock loading exceeds positive-shock loading for 46/53 full-train fits (median difference 0.008992); this is descriptive fitted asymmetry, not a coefficient-significance or universal leverage-effect claim.

## Changed results and reproducibility

The complete original notebook/model/backtest snapshot is preserved locally. Public checkouts retain compact historical CSVs, fitted coefficients, exact forecast-column fingerprints and common masks under `audit_snapshot_20261009T200003Z/`; they do not need the multi-gigabyte historical ledgers. Notebook 07's cache-key code was hardened in the earlier audit. The pre-handoff run corrects fresh/cache CSV container formatting and invalid-input acceptance, including zero-observation volatility likelihoods. It retains the original Monte Carlo convention. All fitted coefficients, forecast values and numerical result tables remain unchanged. The strict pre-handoff validator independently reconstructs forecasts and targets and permits no changed forecast columns or numerical metric rows. Its result is embedded in audit_reproducibility_manifest.json. Notebook 08 ran top to bottom after the source corrections, including all 47 strategies,10 common comparisons and 6fee/slippage scenarios. **21 embedded checks** pass; **14 external tests** pass (one deliberately documents the calendar limitation). Independent forecast/normalization scripts run without fitting models. Stored outputs were regenerated by executable code, never edited as numbers.

| strategy | gross total return old | gross total return new | total return old | total return new | trades change |
| --- | --- | --- | --- | --- | --- |
| S0 | -13.9977% | -15.6988% | -90.5186% | -92.6717% | 62687 |
| S1 | -0.5522% | 0.2692% | -83.0283% | -85.4293% | 69846 |
| S2 | -0.7214% | 0.1463% | -81.4602% | -84.0295% | 69846 |
| S3 | -0.5957% | 0.2326% | -83.0393% | -85.4381% | 69846 |
| S4 | 8.7435% | 9.8621% | -81.4352% | -84.0291% | 69846 |
| S5 | 6.7947% | 7.6590% | -80.0508% | -82.8262% | 69846 |
| S6 | 7.4308% | 8.2761% | -81.6641% | -84.2644% | 69846 |
| S7 | 0.1236% | 0.1374% | -27.3205% | -29.2506% | 69846 |
| S8 | 0.1753% | 0.2112% | -25.8149% | -27.7285% | 69846 |
| S9 | 0.1071% | 0.1206% | -27.3451% | -29.2760% | 69846 |

The only changed backtest results are the common-cohort rows caused by the corrected mask. Available results are unchanged; supplementary volatility tables differ by explicitly recorded horizon/cohort. There is no new strategy or test-selected model.

Reproduce from repository root using the existing scientific environment: execute08, then execute `09_final_audit_07_08.ipynb`. The audit notebook invokes the retained scripts in `audit_code/`, checks all required inputs, displays bounded tables and regenerates the six requested deliverables. It requires the original feature/model/backtest files; missing inputs stop execution, not fabricated metrics. `audit_reproducibility_manifest.json` records source/code/output hashes and snapshot location.

## Remaining limits and what to tell Nikolai

The evidence supports minute-return heavy tails and volatility clustering, modest and unstable volatility forecast gains at a precisely defined horizon, and the absence of positive net results in the tested exchange-fee scenarios. It does not establish executable alpha. Explain that high turnover can overwhelm a small predictive edge; zero-return class imbalance, forecast loss and direction-profit objectives are different, and statistical predictability is not a guarantee of signed return magnitude after costs.

The54-product universe and test are retrospective; close fills are simulated; lot quantities are fractional; capital is normalized with daily allocation; no integer lots, margin/funding, spread, broker charges, impact or capacity are certified. Fees are 2026assumptions, with unresolved source scope. The official historical trading calendar is missing. No strategy is designated the test-period winner. These are presentation caveats, not reasons to hide losses or delay cases.

English handoff: `presentation_findings.md`. Use the gross/net comparison, explicit fee title, matched-horizon volatility table and limitations together.
