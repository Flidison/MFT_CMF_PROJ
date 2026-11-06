# MFT Research Validation

This assessment separates mathematical implementation, internal accounting and
economic realism. A passing test addresses the first two questions within its
scope; it does not establish tradable alpha or an untouched holdout.

## Data and statistical calculations

The independent raw-data pass covered 77 files and 44,019,900 raw rows.
After the stated duplicate/conflict reconciliation the count is 44,011,860.
Exact duplicates, conflicting fields, negative activity, zero volumes, gaps and
delivery changes are recorded explicitly rather than silently winsorized.

The current 54-product window contains:

| Period | Bars | Valid one-minute log returns |
|---|---:|---:|
| Train, 2016–2019 | 15,067,695 | 14,912,832 |
| Test, 2020–18 October 2021 | 7,671,030 | 7,587,843 |
| Full | 22,738,725 | 22,500,675 |

A valid return is log(C_t)−log(C_t−1) inside one delivery contract and an exact
one-minute uninterrupted segment. First/boundary returns remain unknown. Rolling
statistics and lag pairs preserve the minute clock; deleting missing or
zero-volume rows cannot create shorter artificial lags. Zero-volume returns
remain in the main statistical sample and their sensitivities are labelled.

Primary ACF is pair-specific Pearson correlation over eligible within-segment
pairs. This is distinct from a full-series autocovariance normalization and from
the equal-segment mean retained from notebook 02. Both estimands are valid when
identified correctly. Independent direct correlations and a dense Bartlett HAC
matrix reproduce the implementation. The active code does not introduce a
separate empirical PACF analysis; AR(2)'s stationary parameter transform is
checked as part of model estimation.

Daily influence-score HAC uses stated 20/60-date bandwidths, minimum date counts
and BY multiple-testing families. Its finite-moment/asymptotic assumptions remain
material under heavy tails and regime changes. Pointwise intervals are not
simultaneous confidence bands. A descriptive clustering label is not a formal
stationarity or long-memory result. The event-study contrasts in notebook 06
measure conditional future price changes, not trading profit.

## Estimation, targets and leakage

Standalone mean and variance models use 2016–2019, then frozen coefficients.
Composite volatility feature fits use 2016–2018; direction/logistic normalization
uses settled 2019 labels. This prevents fitting a feature map on its calibration
or test targets. State updates use available returns and restart at gaps,
delivery changes and nonfinite observations.

Independent checks cover ARMA innovations, GARCH/GJR/EGARCH equations, parameter
transforms, likelihood gradients and exact forecast windows. Gaussian QML is a
working estimation criterion, not evidence that empirical innovations are normal.
Optimizer success alone is insufficient: the corrected code rejects a
zero-observation volatility likelihood and preserves failure/coverage records.

GARCH persistence is alpha+beta. With stored positive/negative GJR shock loadings,
the symmetric-unit-variance quantity is beta+(positive+negative)/2. The imposed
ceiling below 0.999 is deliberate. It limits conclusions about the boundary and
does not prove stationarity of the full financial history. EGARCH beta describes
log variance and must not be interpreted as the same persistence quantity.

Realized variance is the mean of future training-demeaned squared minute returns.
Standalone h5 covers t+1…t+5. Planned delayed-entry holding risk covers t+2…t+6 and
uses the sum, rather than the mean, of those five conditional variances.
Evaluation must retain the matching target, horizon, product set and origin mask.

The original fixed-horizon, 2,048-path antithetic Gaussian Monte Carlo convention
is retained. Different requested horizons can produce different finite paths
without bias. A candidate common-prefix rewrite was not shipped. Independent
matrix-convolution forecasts reproduce the retained convention; finite simulation
precision and large finite EGARCH forecasts remain limitations. Clipping guards
are recorded, not treated as proof of economic stability. Unverified extreme NI/FU
source prints remain in the data pending external confirmation.

No mechanical use of test targets was found in final trading admission.
Nevertheless, the 54-product universe was chosen retrospectively and this test
history has been viewed repeatedly. Frozen chronological fitting does not remove
research-selection bias. A new prospective experiment or independent later
dataset is required for an untouched confirmation. Changing the existing sample
or hypotheses would not repair that historical fact.

## Forecast evidence and cohort comparability

The original standalone comparison has 53 eligible products; SA has only 19
training dates against a minimum 20. All-seven composite direction uses 46.
Notebook 08's disclosed standalone SA extension gives 54 planned-hold products.
These are different cohorts, not contradictory counts.

On 54 matched products and 1,184,638 origins for the planned t+2…t+6 window,
equal-product mean ΔQLIKE against EWMA is approximately:

| Period | GARCH | GJR |
|---|---:|---:|
| 2020 | −0.003889 | −0.004108 |
| 2021 | +0.000345 | +0.000333 |
| Combined | −0.001858 | −0.001977 |

Negative loss differences are favourable. The average gain changes sign in 2021.
A supplementary daily-HAC comparison gives combined 95% intervals approximately
[−0.009101, +0.005386] and [−0.009447, +0.005492]; neither establishes a stable
improvement. These nominal diagnostics do not create a new holdout.

Notebook 07's separate t+1…t+5/common-all-six/53-product comparison instead has
positive mean GARCH/GJR differences, approximately +0.010165/+0.010185.
Pooling these statements without their window/cohort labels is invalid.
Fixed five-minute scores do not evaluate variable delayed-exit holding horizons.

## Backtest reliability and execution realism

Independent reconstruction covered all 34,806,565 saved strategy/cohort ledger
rows and all 54 products. It checked source closes, absolute-quantity fees,
multipliers, one-minute entry delay, earliest eligible exits, nonoverlap,
contract runs and daily aggregation. Maximum daily net error was 3.47×10⁻18.
The implementation is internally consistent for its declared experiment.

There are 5,974 distinct delayed-exit events, with maximum duration 30 minutes.
Some appear in multiple strategy ledgers; repeated rows are not distinct market
incidents. One observed intraday break is shared by several variants. No actual
day-to-night contract/trading-day misclassification was found, but calendar-date
logic can permit it synthetically. An official dated exchange calendar is still
needed to certify that convention.

The exposure cap is defined at the signal price. It is not a guarantee of a
constant marked-to-market leverage or margin balance after a price move.
Fractional lots, normalized capital and close fills are research assumptions.
Positive minute volume does not certify spread, depth, queue position or capacity.

The August 2026 workbook scenario is not reconstructed historical 2020–2021 fees.
I's divisor, AG near/far mapping and SC front-month scope remain unresolved.
Broker, spread and impact costs are absent from the base. Sensitivities are
explicit assumptions rather than calibrated execution estimates.

Daily compounding, cash sleeves, initial-equity drawdown, calendar annualization,
historical VaR and exact fractional-tail ES reconcile independently. Gross and
net compound on separate paths; additive fee attribution uses one net-capital
path. Across 47 variants, 28 are gross-positive and none net-positive in the
specified base; S0–S9 have 9/10 gross-positive and 0/10 net-positive. This supports
the stated cost-drag conclusion within the scenario, rather than a profitable
live strategy.

## Previous-audit concerns revisited

| Concern | Current classification |
|---|---|
| Retrospective universe; repeated test inspection | Methodological limitation; requires independent validation |
| Persistence constraints | Legitimate, explicit modelling constraint |
| EGARCH extreme predictions/finite simulations | Numerical/economic model limitation; equations independently reproduced |
| Different Monte Carlo paths across horizons | Legitimate finite-simulation convention; original scheme retained |
| Target/forecast alignment | Independently verified for original and delayed windows |
| Different evaluation cohorts | Explicit scope difference; matched comparisons required |
| Fee units and conditional product scope | Resolved conversion arithmetic; remaining source assumptions disclosed |
| Execution chronology/delayed exits | Internally reconciled; close-fill realism remains unverified |
| Calendar versus exchange trading day | Documented limitation with a synthetic counterexample |
| Portfolio accounting | Independently reconciled |
| Notebook state/cache/export reproduction | Corrected/verified; expensive legacy walk-forward fits partly reused under explicit equivalence checks |

## Presentation consistency

The deck was not redesigned. Its broader research coverage must be distinguished
from the active nine-notebook experiment.

- Slide 2 shows 22,681,635 bars and 22,445,422 returns, versus 22,738,725 and
  22,500,675 in this pipeline. If it describes this universe, those totals need
  updating; otherwise the alternative source/window must be identified.
- Slide 13 includes BC, LH, PF and PG, which are absent from this final universe.
  Tail-method claims cannot be transferred between these product sets.
- Several early slides use block-bootstrap IC scans, AR(5)/EWMA cleaning,
  GPH/Hill/GEV/GPD or 90/90 normal-VaR rejection counts. Their complete source
  calculations are not in the active 01–09 chain. They remain unverified in this
  scope, rather than being declared false or repaired with a different experiment.
- The later ACF, matched-horizon GARCH/GJR and gross/net panels were reconciled
  with current outputs and the local supporting diagnostics. Their cost-drag
  and unstable-model-gain conclusions remain supported.
- Slide 25 combines conclusions from these different sources and needs explicit
  source/cohort labels before being presented as one reproducible experiment.

New independent data are needed for external alpha validation; historical tariff
and trading-day records for execution certification; external market prints for
suspect extremes; and complete source calculations for the broader deck.
