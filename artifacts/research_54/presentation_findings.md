# MFT Futures Research — verified findings for Nikolai

**Historical backtest under August 2026 exchange-fee assumptions.**

**The main conclusion:** return distributions exhibit heavy tails and volatility clustering, but this research does not establish positive tradable alpha after the specified exchange fees.

## Return properties

Across 54 products in 2020–18 October 2021, median lag 1 return ACF is -0.0811; absolute-return ACF is 0.2314. Median excess kurtosis is 12.06; all 54 products have heavier 3-sigma tails than a Gaussian benchmark. These are descriptive minute-bar findings, including microstructure/zero-volume effects.

## Volatility forecasting

For the planned Notebook 08 holding window t+2…t+6, 54 products and 1,184,638 matched origins, median forecast/realized-volatility correlation is 0.5452 (GARCH), 0.5453 (GJR), 0.5450 (EWMA). Equal-product mean deltaQLIKE versus EWMA is -0.001858/-0.001977; 30/54 and 31/54 products improve. The gain is small and unstable: in 2021 the deltas turn positive (+0.000345/+0.000333), with only 25/54 and 25/54 products improving. QLIKE uses a floor of 1e-8×training variance.

Do not mix this window with 07's original t+1…t+5/common-all6 result: that original comparison has **worse** average GARCH/GJR QLIKE than EWMA. All scopes are preserved in the comparison CSV. Variable delayed-exit horizons are not scored by the fixed five-minute volatility table.

EGARCH also has 6 finite but extreme planned-hold variance forecasts above1 on 4 products. These were retained and independently reproduced; numerical convergence does not establish stable forecasting.

GJR estimates have larger negative-shock loadings on 46/53 original full-train files. This is descriptive asymmetry, without a coefficient-significance claim. SA is an explicit Notebook 08 extension with only 19 training dates; 07's original eligibility remains 53/54, and composite-model coverage is 46/54.

## Gross versus net

**28/47** tested available-universe variants have positive gross return; **0/47** have positive net return. S0–S9 have 9/10 positive gross results and 0/10 positive net results; corrected common-cohort results also have 0/10 positive net results. No test-period winner is selected.

| Strategy | Gross return | Net after exchange fees | Net + 0.5 bp/side | Net + 1 bp/side |
| --- | --- | --- | --- | --- |
| S0 | -25.61% | -96.76% | -99.46% | -99.91% |
| S1 | 2.19% | -90.46% | -98.09% | -99.62% |
| S2 | 1.99% | -89.54% | -97.79% | -99.53% |
| S3 | 2.15% | -90.47% | -98.09% | -99.62% |
| S4 | 11.54% | -87.92% | -97.11% | -99.31% |
| S5 | 8.60% | -87.12% | -96.76% | -99.19% |
| S6 | 9.85% | -88.11% | -97.16% | -99.32% |
| S7 | 0.14% | -29.25% | -43.86% | -55.47% |
| S8 | 0.21% | -27.73% | -41.96% | -53.40% |
| S9 | 0.12% | -29.28% | -43.90% | -55.51% |

The table shows separately compounded returns. Exchange-fee accounting contributions must use a common net-capital path; they are not gross compounded return minus net compounded return. Base includes exchange fees only. **Broker fees, bid-ask spread and slippage are excluded from the base**; 0.5/1 bp per side are additional sensitivity assumptions, not a complete transaction-cost model. I's unit divisor, AG contract-month scope and SC front-month treatment remain unresolved.

## Audit changes and limitations

Corrected the S0–S9 common mask, added fit-cache lineage validation, and included missing runtime settings in 07 cache keys. The pre-handoff input-validation and serialization corrections preserve every fitted coefficient and forecast; those predictions and scores are independently checked. All 47 original available-universe returns are unchanged; common-cohort values were recalculated. Independent full-ledger checks found no contract crossings or position overlaps. There are 5,974 distinct delayed-exit events, with maximum 30 minutes, including one RR intraday-break crossing; those positions remain in PnL.

The universe was selected retrospectively using some test history; 2020–2021 is not pristine. Execution is a close-price simulation, not bid/ask/order-book evidence. Fractional contracts and daily normalized capital differ from real lot/margin constraints. The exchange calendar and historical fee schedule are not reconstructed; broker charges, spread, impact and capacity are unverified. **Present this as a reproducible research experiment, not production-ready trading performance.**

Suggested verbal message: “We confirm heavy tails and volatility clustering. Some volatility forecasts show modest gains at the exact planned horizon, but those gains are unstable and do not translate into positive net performance under our exchange-fee scenarios. We fixed the common-cohort comparison and reconciled the PnL independently; the remaining limits are explicit.”
