# Time-series forecast findings

**AR(1):** one-minute mean MSE skill versus zero is 0.935% (instrument median 0.704%); 70/76 instruments improve. Against the training-mean forecast, 70/76 improve. Median sign accuracy among nonzero targets is 56.75%. Inspect horizon and evaluation-half tables before interpreting this as stable directional predictability.

**MA(1):** one-minute mean MSE skill versus zero is 0.907% (instrument median 0.648%); 69/76 instruments improve. Against the training-mean forecast, 69/76 improve. Median sign accuracy among nonzero targets is 57.35%. Inspect horizon and evaluation-half tables before interpreting this as stable directional predictability.

**ARMA(1,1):** one-minute mean MSE skill versus zero is 0.875% (instrument median 0.627%); 68/76 instruments improve. Against the training-mean forecast, 68/76 improve. Median sign accuracy among nonzero targets is 56.43%. Inspect horizon and evaluation-half tables before interpreting this as stable directional predictability.

**GARCH, 1 minutes:** QLIKE improves on historical variance in 72/76 instruments, on trailing-30-minute variance in 76/76, and on EWMA in 51/76. Median QLIKE differences are -10273.6025 versus trailing variance and -0.0094 versus EWMA (negative is better). Median origin-level forecast/realized-variance correlation is 0.248. Equal-file mean QLIKE change versus constant variance is -0.2017, while the median is -0.3546; large disagreement exposes tail sensitivity. These are forecasts of movement magnitude, not its sign.

**GARCH, 5 minutes:** QLIKE improves on historical variance in 71/76 instruments, on trailing-30-minute variance in 76/76, and on EWMA in 45/76. Median QLIKE differences are -32777.5692 versus trailing variance and -0.0036 versus EWMA (negative is better). Median origin-level forecast/realized-variance correlation is 0.361. Equal-file mean QLIKE change versus constant variance is 0.0268, while the median is -0.3170; large disagreement exposes tail sensitivity. These are forecasts of movement magnitude, not its sign.

**GARCH, 30 minutes:** QLIKE improves on historical variance in 73/76 instruments, on trailing-30-minute variance in 73/76, and on EWMA in 40/76. Median QLIKE differences are -59265.6986 versus trailing variance and -0.0042 versus EWMA (negative is better). Median origin-level forecast/realized-variance correlation is 0.444. Equal-file mean QLIKE change versus constant variance is 0.3330, while the median is -0.2541; large disagreement exposes tail sensitivity. These are forecasts of movement magnitude, not its sign.

**QLIKE floor sensitivity, 1 minutes:** GARCH beats trailing variance in 67-76 instruments across the four floors, and beats EWMA in 49-52. Use this range alongside the default-floor result; very large gains against a zero trailing variance are floor-sensitive.

**QLIKE floor sensitivity, 5 minutes:** GARCH beats trailing variance in 64-76 instruments across the four floors, and beats EWMA in 41-45. Use this range alongside the default-floor result; very large gains against a zero trailing variance are floor-sensitive.

**QLIKE floor sensitivity, 30 minutes:** GARCH beats trailing variance in 55-73 instruments across the four floors, and beats EWMA in 38-40. Use this range alongside the default-floor result; very large gains against a zero trailing variance are floor-sensitive.

**Parameter diagnostics:** 11 GARCH fits are near the imposed parameter bounds; inspect the parameter report and individual forecast losses before deployment. Better median performance does not imply uniform improvement across instruments.

**Limits:** parameters are fixed after the initial calibration period; results are descriptive chronological-holdout comparisons, not independent post-selection significance tests. All comparisons retain zero returns and extreme observations; only forecast availability and explicit calibration eligibility affect coverage. A positive directional event return can coexist with poor MSE skill.
