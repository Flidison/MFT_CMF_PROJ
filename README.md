# MFT futures research

Minute futures data: data quality, statistical dependence, direction and volatility
forecasts, and exploratory trading strategies. The notebooks are working notes
with code, tables and plots. Setup, methods and interpretation are collected here.
Generated datasets and result files are kept locally.

## Notebooks

| Notebook | Contents |
|---|---|
| [01_data_quality_check.ipynb](01_data_quality_check.ipynb) | Data cleaning, duplicate records, contract changes and minute gaps |
| [02_research_statistics_features.ipynb](02_research_statistics_features.ipynb) | Segment-aware features, descriptive statistics and correlations |
| [03_strategies_hypotheses.ipynb](03_strategies_hypotheses.ipynb) | Original 77-file hypotheses, forecasting models and walk-forward experiments |
| [04_liquidity_activity.ipynb](04_liquidity_activity.ipynb) | Liquidity, activity and selection of the 54-product universe |
| [05_research_statistics_features_54.ipynb](05_research_statistics_features_54.ipynb) | Return dependence, tails and volatility clustering for 54 products |
| [06_strategies_hypotheses_54.ipynb](06_strategies_hypotheses_54.ipynb) | Conditional-return hypotheses with training thresholds |
| [07_forecasting_models_54.ipynb](07_forecasting_models_54.ipynb) | ARMA, GARCH, GJR, EGARCH and direction forecasts |
| [08_backtest_fees_risk_54.ipynb](08_backtest_fees_risk_54.ipynb) | Execution, product-specific fees, position sizing and portfolio risk |

Run from the repository root in separate Python kernels. The original study runs
**01 → 02 → 03**. The 54-product study runs **01 → 02 → 04 → 05 → 06 → 07 → 08**;
it reuses definitions from notebook 03 without executing that notebook's experiments.
Saved cell outputs and figures are included.

## Setup

Use Python 3.11:

```bash
python3.11 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m ipykernel install --user --name mft-research --display-name "MFT research"
```

Open the notebooks in a Jupyter-compatible editor and select the `MFT research`
kernel. JupyterLab can be installed with `python -m pip install jupyterlab`.

## Inputs

Place the original 77 market CSV files in `fut_data/`. They are available as the
`raw-data-*.tar.gz` assets in the existing
[research snapshot release](https://github.com/Flidison/MFT_CMF_PROJ/releases/tag/research-snapshot-v1).
Using the GitHub CLI:

```bash
gh release download research-snapshot-v1 --repo Flidison/MFT_CMF_PROJ \
  --pattern 'raw-data-*.tar.gz' --dir release-assets
for archive in release-assets/raw-data-*.tar.gz; do
  tar -xzf "$archive"
done
```

Notebook 08 also requires the original commission workbook used for the research.
Before starting its kernel, set `MFT_FEE_WORKBOOK` to that workbook's absolute path.
It is copied into `artifacts/research_54/backtest/inputs/commission_schedule.xlsx`
on first execution. Market data, the workbook, intermediate datasets, model caches
and exported tables are excluded from Git. The notebooks create their output
directories under `artifacts/` when run.

## Tests

```bash
python -m pytest -q tests
```

Tests load calculation definitions directly from the notebooks and use synthetic
inputs. They cover return and forecast alignment, variance recursions, likelihood
gradients, fees, execution chronology, risk metrics and cache serialization.
Market data and saved calculation files are not needed to run them.

## Data and features — 01–02

An instrument is one supplier file; `symbol` identifies a delivery contract.
The 77 files contain 3,034 delivery symbols. Timestamps are supplier-local and
timezone-naive. Prices are supplier-selected contract quotes, without an assumed
back adjustment or verified roll rule.

Notebook 01 assigns source-row IDs before sorting. Only exact copies are removed.
For conflicting `(symbol, timestamp)` records, each field is retained when all
variants agree and otherwise becomes missing. The minimum source ID identifies
the reconciled record; the original variants are saved separately. Prices are
not filled, adjusted or winsorized. Suspicious prices and activity values are
flagged rather than automatically deleted.

The saved dataset has 44,011,860 bars after removing 7,636 exact copies and 404
redundant variants; reconciliation introduces 430 unknown field values.
Quality thresholds label records for inspection and do not change the sample.
The jump flag is the larger of 1% and the contract's median absolute move plus
`10 * 1.4826 * MAD`, with a 1% fallback below 100 reference edges.

Gap classification compares clock minutes on up to ten neighboring observed
dates on either side, within 45 calendar days. With at least five reference dates,
presence of at least 80% suggests a missing bar and at most 20% a regular break.
This is a retrospective diagnostic, not an exchange calendar or a trading input;
it does not fill bars or determine feature boundaries.

Notebook 02 starts a segment at a contract change, ambiguous timestamp or
nonconsecutive minute. Returning to an earlier contract does not reconnect its
history. Missing prices retain their positions; model states additionally restart
after a missing return. Lags never compress gaps or missing observations.

For finite positive closes within a segment:

```text
simple_return[t] = Close[t] / Close[t-1] - 1
log_return[t] = log(Close[t] / Close[t-1])
bar_range[t] = High[t] - Low[t]
rolling_volatility[t] = sample_std(last 30 log returns, including t)
normalized_return[t] = simple_return[t] / rolling_volatility[t]
```

Rolling volatility requires 30 finite returns. Nonpositive or missing volatility
leaves normalization undefined. Open interest remains a level; activity log
transforms retain their finite `x > -1` domain. Sample standard deviations use
`ddof=1`; quantiles use linear interpolation. Skewness and Fisher excess kurtosis
use bias-corrected estimators and are undefined for constant series. Strict return
exceedances use decimal source prices to resolve threshold ties.

The correlation interface calculates `corr(Tx(x[t]), Ty(y[t-lag]))`: positive lag
places the right-hand feature in the past. Identity, absolute and squared
transforms and segment-contained windows are available. The exhaustive screen
uses absolute values, all ordered pairs of 13 features and lags 1/2/3/5/10:
845 configurations per file, 65,065 in total.

Each defined segment coefficient receives equal weight. The significance test
concerns the mean segment coefficient, rather than a pooled-bar correlation.
Centered coefficients are summed by segment-start date; Bartlett HAC uses 20 and
60 observed-date lags on a common date clock, with at least 90 dates. The screen
uses the larger two-sided normal p-value, global Benjamini–Yekutieli correction
and `q < 0.05`. Undefined p-values count as one only in multiplicity accounting.
Pointwise 95% intervals use the larger standard error. Excluding the Open/lagged
Close pair changes the display, not the correction family. There are 42,458
significant rows in the saved screen.

Price-level persistence, short-segment correlation bias and overlapping rolling
windows affect interpretation. Absolute-value dependence measures magnitude and
activity; it does not supply a future return sign.

## Original 77-file study — 03

The notebook contains three separate experiments. Their samples, targets and cost
assumptions should not be combined with the later 54-product study.

### Conditional events

The first 30% of observed dates calibrate each instrument's quantiles; later dates
evaluate horizons 1/2/3/5. Signals are known at close `t`. The target is
`Close[t+h] / Close[t] - 1` inside one continuous segment. Events may overlap;
these are gross conditional effects, without execution or an equity account.

| Condition | Training thresholds |
|---|---|
| Return and volume | Positive Q90 / negative Q10 return; volume Q80 / Q20 |
| Range and volume | Range Q90, return sign; volume Q80 / Q20 |
| Volatility regime | Return Q90 / Q10; trailing volatility Q80 / Q20 |
| Normalized return | Positive Q90 / negative Q10 normalized return |

Momentum follows the event sign; reversal takes its negative. Strict signs exclude
zero-return events. Tied high/low quantiles may overlap and are reported as such.
Pooled statistics weight events equally; instrument summaries weight instruments
equally. The ordinary one-sample t-tests and t intervals are exploratory because
events overlap and the history informed hypothesis selection. Momentum and
reversal on the same events are exact negatives, not separate discoveries.

### Fixed-parameter forecasts

The first-30%-of-dates split also fits AR(1), MA(1), ARMA(1,1) and GARCH. Returns
are centered and scaled using calibration moments only. Parameters remain fixed
in evaluation; filter states update with available observations and restart at
boundaries or missing returns. ARMA uses conditional least squares, initialized
innovations and coefficient bounds of ±0.98, rather than exact unconditional
state-space likelihood. Deterministic initial values are compared on training
loss; failed and boundary fits remain visible.

Mean horizons are 1/2/3/5; variance horizons are 1/5/30. Mean targets are cumulative
log returns. Variance targets are future mean squared returns around the fixed
training mean, not future sample standard deviations. Benchmarks are zero and
training mean for returns; historical variance, EWMA(0.94) and trailing-30-minute
variance for volatility. QLIKE floors only predictions. This experiment repeats
scoring at floor ratios `1e-8/1e-6/1e-4/1e-2` of training variance without refitting.

### Walk-forward experiment

The research window starts in 2015, with at least 60 observed dates for warm-up,
a 252-date trailing training window and refits every 63 dates. Validation is
2018–2019; evaluation begins in 2020. ARMA order is selected by training BIC and
frozen before evaluation. Logistic scaling uses each historical training window;
its no-trade threshold uses validation only. Historical volatility forecasts,
not retrospectively fitted states, supply standardized-return predictors.

Signals use close `t`; assumed entry is close `t+1` and exit close `t+6`.
The six-minute grid prevents overlap. Breakout uses the preceding 20 bars;
expansion divides forecast volatility by its previous 30-forecast median, with
threshold 1.2. Permitted clock minutes require at least ten historical examples
and 99% interval completeness. Missing next-minute entries are cancelled; an
entered position without an eligible exit stops the calculation. This experiment
retains zero-volume close fills, an optimistic execution assumption.

Volatility sizing uses a 0.1% five-minute target, 0.001% volatility floor and
leverage cap of three. Fixed-size controls use the same direction score. Turnover
per allocated capital is `abs(position) * (1 + exit_price/entry_price)` and the
main cost is 1 bp per side; 0/0.5/1/2 bp are sensitivity scenarios. Each of the
77 instruments retains an equal capital sleeve, including cash when unavailable.
Trade PnL sums within a day and portfolio capital compounds daily.

Paired comparisons use five-date moving-block bootstrap with 300 deterministic
replications, daily HAC with five lags and BY adjustment within the stated test
families. The same resampled dates preserve cross-instrument dependence. The
representative strategy is chosen on validation Sharpe; evaluation rankings do
not revise that choice. Probability-bucket Sharpe contributions are additive,
unannualized contributions rather than standalone portfolio Sharpes.

The saved walk-forward direction/trading cohort contains 58 instruments and
935,719 completed intervals; standalone volatility covers 70. Raw ARMA and core
logistic strict sign accuracy are 50.39% and 50.33%. None of S0–S9 is net positive
at 1 bp per side; validation-selected S8 returns −19.12%. Significant
asymmetric-logistic return differences are negative, and the tested sizing does
not improve net Sharpe against its fixed-score controls.

## Universe selection — 04

The observed 2016–2021 window ends on 18 October 2021 and contains 1,407 dates.
Dates with daytime bars (`06:00–18:00`) in any file define the empirical calendar.
Evening bars map to its next date; after-midnight bars map to the first calendar
date on or after their date. These are working labels, not official trading days.

Activity is positive-volume dates divided by the common 1,407-date denominator.
Short histories therefore receive a lower score even if active on every observed
date. The activity-only comparison retains 43% → 54 files and 80% → 42 files.
The final universe instead requires all of:

- Activity at least 30%: at least 423 positive-volume dates.
- Zero-volume minutes at most 38% of recorded valid-volume bars.
- Problematic bars at most 0.1% of all recorded bars.

Problematic bars are the union of invalid activity fields, invalid/inconsistent
OHLC and zero-volume/turnover contradictions. Missing minutes are not inserted.
The zero-volume limit was raised from 30% (52 qualifying files) to 38% to obtain
54 products; it is a sample-size choice. B, CY, NR and RR supplement the earlier
50-product set.

All eligible products are retained, ranked by mean daily monetary turnover.
Ties use daily volume, closing open interest, zero-volume share and filename.
Daily means use each product's observed dates, including valid zero sums;
incomplete field-days are omitted rather than filled. Closing OI is a snapshot,
not a daily sum. Vendor monetary units are assumed comparable. Universe selection
uses the full window and was not available at the start of the backtest.

## Statistics and event studies — 05–06

Both stages retain all 54 selected products. Training is 2016–2019; test is
2020–18 October 2021, split by bar calendar timestamp.

Notebook 05 reuses the original features. Primary ACF pools valid exact-lag
within-segment pairs; the equal-segment estimate is separate. Its correlation
influence score is `u*v - rho*(u*u + v*v)/2` for standardized pairs. Scores are
summed by the later endpoint's date; uncertainty uses 20/60-date HAC and at least
90 dates. BY correction applies to the ACF family within each period. Both
endpoints must share a segment and period. Positive-volume sensitivity keeps the
original minute clock. Median/IQR plot bands describe product dispersion, not
confidence intervals.

Tail statistics retain extremes and compare 3/5/10-standard-deviation exceedances
with a normal benchmark. Product-standardized CCDFs use equal product weights.
NI's −8.62% log return on 22 May 2020 and FU's −10.07% on 10 February 2021 remain
in the data; their source bars need external price confirmation. Excess kurtosis
alone does not establish a power-law tail or existence of a fourth moment.

Clustering labels use absolute-return ACF at lags 5/10/30: `strong` requires all
three coefficients ≥0.10 and significant; `persistent` requires at least two
≥0.05 and significant; `localized` requires one positive significant coefficient.
Otherwise labels are `not_detected` or `insufficient`. These are descriptive
rules. A seasonality sensitivity shrinks training minute-of-day mean absolute
returns toward the overall mean with 20 pseudo-observations; unseen minutes use
factor one. Squared-return and rolling-volatility diagnostics are separate.

The saved test medians are ACF(return,1) −0.0811, ACF(abs(return),1) 0.2314 and
excess kurtosis 12.06. Clustering labels are 43 strong / 11 persistent, or
40 / 14 after seasonal adjustment. These labels do not select models.

Notebook 06 applies the four conditional-event families above, five-return
momentum and prior-20-bar breakout. Training quantiles are frozen. Targets are
`Close[t+delay+h]/Close[t+delay]-1` for horizons 1/2/3/5 and delays 0/1, requiring
a complete segment and period. A delayed target is a price-response test, not
an assumed fill.

Reported contrasts are mean future return after positive events minus that after
negative events, in basis points. Positive means continuation; negative means
reversal. Inference requires 100 events and 90 dates per direction, daily HAC and
BY correction. Aggregation uses equal product weights and accounts for synchronous
dates. Inferential cohorts can change with period/horizon; the separate all-defined
descriptive mean must not be substituted for them.

At test horizon five and delay one, 6/9 aggregate contrasts pass BY, all in the
reversal direction. The 486 product/condition tests contain 54 reversal labels,
329 not detected and 103 insufficient. Return/high-volume contrasts attenuate
from −2.49 bp without delay to −0.65 bp with delay; normalized-return contrasts
from −2.81 to −0.52 bp. These are event-study contrasts, not strategy profits.

## Forecasting — 07

Standalone models fit on 2016–2019 and remain fixed in test. Eligibility requires
20 dates and 1,000 finite training returns: 53/54 products qualify; SA has only
19 training dates. The seven-direction-model common cohort contains 46 products.
Coverage failures remain missing rather than becoming zero forecasts.

Mean models are AR(1), MA(1), AR(2), ARMA(1,1), zero and training mean, at horizons
1/2/3/5. Conditional Gaussian CSS compares orders on a common two-return burn-in.
AR(2) uses stationary partial-autocorrelation parameters; other coefficients are
bounded at ±0.98. Composite raw/standardized ARMA uses training BIC. Logistic uses
fixed L2 penalty 0.001 and target `future_return > 0`, with zero in class zero.
Strict sign accuracy separately excludes zero targets and neutral predictions.

For composite models, volatility features fit on 2016–2018; direction models and
their scaling use settled 2019 labels. The feature map remains fixed in test.
This differs from notebook 03's rolling refits. The composite target is
`log(Close[t+6]/Close[t+1])` on the predetermined six-minute origin grid.

Variance models use Gaussian quasi-likelihood on training-standardized returns:

```text
GARCH: h[t] = omega + alpha*e[t-1]^2 + beta*h[t-1]
GJR:   h[t] = omega + (alpha + gamma*I(e[t-1]<0))*e[t-1]^2 + beta*h[t-1]
EGARCH: log(h[t]) = omega + beta*log(h[t-1])
                    + alpha*(abs(z[t-1])-sqrt(2/pi)) + gamma*z[t-1]
```

GARCH has nonnegative coefficients with `alpha+beta < 0.999`. GJR stores separate
nonnegative positive/negative shock loadings, with their average plus beta below
0.999 under symmetric innovations. EGARCH's log-variance beta has a different
interpretation. Initial standardized variance is one per finite run. Empty
effective likelihoods and failed fits are rejected; bounds and guard hits are
recorded. EGARCH's numerical log-variance guard is ±30.

GARCH/GJR use analytic future-variance recursions. EGARCH averages variance over
2,048 antithetic Gaussian paths with fixed seeds; it does not exponentiate the
mean log variance. Separate requested horizons retain their fixed-horizon random
streams and need not share finite simulation prefixes.

Mean targets are cumulative log returns; realized variance is the future mean of
`(return-training_mean)^2` over the matching horizon. Mean losses are MSE/MAE and
MSE skill against zero. Variance loss is `mean(log(predicted_variance) +
realized_variance/predicted_variance)`; a negative QLIKE difference favors the
candidate. The main prediction floor is `1e-8 * training_variance`. Models share
origins within each comparison and aggregate with equal product weights.

Loss floors `1e-10/1e-8/1e-6` leave the saved GARCH-family differences against EWMA
unchanged; trailing variance is sensitive because it has 1,667 zero forecasts in
the five-minute cohort. Its median QLIKE difference changes approximately
356.24 → 3.56 → 0.0415. Observations remain in all scenarios.

Saved one-minute AR(1) median MSE improvement is 0.64%. Delayed five-minute strict
sign accuracy is 50.06% for raw ARMA and 50.40% for core logistic. GARCH's median
forecast/realized-volatility correlation is 0.558, but median five-minute QLIKE
differences against EWMA are positive: approximately 0.0022 / 0.0022 / 0.0082 for
GARCH/GJR/EGARCH. Correlation alone does not establish superior loss performance.

Caches require matching feature hashes, computational functions and settings.
Fresh and cached fits export the same full-precision containers;
`REUSE_VERIFIED_CACHE=False` requests fresh estimation.

## Execution, fees and risk — 08

This experiment uses the 54-product forecasts with product-specific costs. It
applies an August 2026 exchange-fee workbook to 2020–2021, not a reconstructed
historical tariff. The 78 workbook rows map by exact product code/exchange.
Conflicting per-mille labels and Notes require explicit divisors: 10,000 by
default, 1,000 for RB/HC/AG/FU/JD/UR. I's unit remains uncertified; alternative
global interpretations are sensitivity scenarios.

Baseline AG uses the far-month columns. SC's close-today waiver is applied across
contracts although the source annotates a front-month condition. Multipliers are
CNY per quoted price unit; T/TF use 10,000 and test-period FU uses ten. Vendor
turnover consistency does not certify every historical contract specification.

Signals form after close `t`; simulated entry is close `t+1`, followed by five
minutes of holding. Missing/invalid/zero-volume entries cancel. An unavailable
exit waits for the earliest valid positive-volume bar within the same contract
run and calendar date. Open positions block overlap; unresolved positions stop
aggregate PnL. Permitted clock minutes require ten training examples and 99%
complete twelve-minute intervals, including six reserve minutes after planned
exit. Future target availability never admits a trade.

ARMA trades its forecast sign; logistic uses `2*p-1` with fixed threshold 0.5.
Volatility sizing targets 0.1%, with leverage cap three and volatility floor
`1e-5`. Holding risk sums conditional variances for steps 2–6, excluding entry
delay. This additive proxy omits future cross-covariances and is not a joint
ARMA–GARCH conditional variance. Common S0–S9 admission requires only forecasts
used by those ten strategies. SA's standalone extension uses 6,258 returns on
19 dates; insufficient early history still excludes its composite models.

Quantity is fixed from the signal price before either fill:

```text
quantity / capital = position / (signal_price * multiplier)
gross PnL / capital = quantity * multiplier * (exit_close - entry_close)
fee per leg = abs(quantity) * (fixed_fee + fill_price * multiplier * rate)
net PnL = gross PnL - exchange fees - broker fees - slippage
```

Quantities are fractional contracts. Slippage shifts entry and exit adversely;
notional fees use those shifted fills. Gross uses unshifted closes and slippage
is a separate deduction. Broker markup is CNY/lot/side. Invalid prices, costs,
multipliers and unrepresentable notionals raise errors. Same-calendar-date trades
use close-today fees; calendar date is not a verified exchange trading day.

Each of 54 products retains 1/54 of beginning-of-day capital, including cash when
unavailable. Nonoverlapping trade PnL sums daily and capital compounds daily.
Idle calendar dates remain; Sharpe annualization uses 365.25, without a risk-free
rate. Drawdown includes starting equity of one. Historical daily-loss VaR95 and
ES95 are reported; ES averages exactly the worst 5% mass with fractional boundary
weight. Empty, nonfinite and inconsistent daily ledgers are rejected.

Gross and net equity compound separately. Their difference is not an additive
fee total: exact PnL/cost contributions use the same net-capital trajectory.
Alternative fee units and +0.5/+1 bp per-side slippage retain the signals,
quantities and timestamps. The baseline excludes broker fees, spread, slippage,
impact and capacity. Of 47 saved variants, 28 are gross positive and none net
positive under the specified exchange-fee scenario.

## Interpretation

The universes are retrospective and the historical sample informed prior research.
Chronological fitting, HAC, bootstrap and multiple-testing correction do not make
this an untouched external holdout. New market data are needed for confirmation.
Standalone, common-cohort and inferential-subset results have different
denominators. ACF significance, forecast loss and executable profit answer
different questions. Extreme EGARCH forecasts remain in evaluation rather than
being removed to improve results.

Minute OHLCV cannot establish executable close fills, integer-lot feasibility,
spread, queue priority, margin requirements or trading capacity. Gap labels,
session permissions and calendar-day accounting do not replace a dated exchange
calendar. Fee scenarios do not certify historical contract tariffs.

Model definitions and conventions: [GARCH](https://arch.readthedocs.io/en/latest/univariate/generated/arch.univariate.GARCH.html),
[EGARCH](https://arch.readthedocs.io/en/latest/univariate/generated/arch.univariate.EGARCH.html),
[multistep forecasts](https://arch.readthedocs.io/en/latest/univariate/forecasting.html),
[HAC](https://www.statsmodels.org/stable/generated/statsmodels.stats.sandwich_covariance.cov_hac.html),
and [BY correction](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html).
