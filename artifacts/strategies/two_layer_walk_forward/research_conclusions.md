# Two-layer research conclusions

**1. Directional predictability.** On a common instrument cohort, baseline nonzero sign accuracy is 47.27%; raw ARMA is 50.39%; logistic direction is 50.33%. Strict sign accuracy excludes zero targets and neutral forecasts; baseline direction coverage is 77.20%. Binary accuracy instead uses positive versus nonpositive targets. These denominators, score calibration and net outcomes must be considered together.

**2. Raw-return ARMA.** Its equal-instrument mean score/return correlation is -0.0026, versus -0.0139 for momentum. This measures incremental out-of-sample association at the specified delayed five-minute horizon, not a proof that futures prices are predictable at arbitrary horizons.

**3. Volatility standardization.** The strongest standardized variant by descriptive holdout nonzero sign accuracy is `D2_ARMA_Standardized_EGARCH` at 50.50%, compared with raw ARMA at 50.39%. Fixed-size paired tests in `controlled_attribution.csv` separate normalization from volatility sizing; this ranking does not change the frozen strategy.

**4. Direct probabilistic direction.** The core logistic model has mean instrument AUC 0.5343 and Brier score 0.2184. Its nonzero sign accuracy differs from raw ARMA by -0.06 percentage points. Calibration and confidence buckets show whether probability magnitude adds useful discrimination.

**5. Standard GARCH.** Median instrument correlation with subsequent realized volatility is 0.511. The lowest equal-instrument holdout QLIKE among all five variance models is `V3_GJR_GARCH`. Realized squared-return variance is noisy; positive correlation alone does not establish superiority over EWMA or trailing volatility.

**6. EGARCH versus GARCH.** The mean paired QLIKE difference is +0.0362; EGARCH improves QLIKE in 22/70 instruments. Negative differences favor EGARCH. Its variance MSE is 7.69e+06 versus 1.85e-08 for GARCH: extreme EGARCH forecasts expose numerical/model fragility. They are flagged and retained, not winsorized.

**7. GJR versus GARCH.** The mean paired QLIKE difference is -0.0006; GJR improves in 36/70 instruments. An asymmetric specification is not automatically better merely because it has an additional parameter.

**8. Signed-shock asymmetry.** Across magnitude buckets, negative/positive ratios of median scale-normalized subsequent volatility range from 1.019 to 1.067. Values above one indicate higher subsequent volatility after negative shocks in that bucket. Instrument-level tables and estimated gamma values must accompany this pooled diagnostic; it is not causal evidence.

**9. Indirect directional value of asymmetry.** Adding asymmetric predictors changes mean AUC by +0.0009 and Brier score by +0.0007. 4/4 sizing comparisons pass the reported BY-adjusted paired mean-return test. These results concern a probabilistic direction model; EGARCH/GJR themselves do not predict a negative or positive return.

**10. Direction plus volatility.** The descriptive primary holdout Sharpe leader is `S8_Logistic_EGARCH` (Sharpe -20.67, net total return -19.12%). The representative chosen strictly on validation is `S8_Logistic_EGARCH` (holdout Sharpe -20.67). The former is a reported ranking, not a deployable selection made before the holdout.

**11. Transaction costs.** 0/10 primary variants have positive net total return at 1 bp per side. The validation-selected strategy has net total return -19.12% and gross PnL -0.0011 versus costs 0.1901 per unit starting equity. The cost grid shows how quickly any gross effect disappears.

**12. Locked-period evidence.** For the validation-selected strategy the daily mean 95% HAC interval is [-0.000350, -0.000296]. Orders, features and thresholds use past/training/validation data, but the historical dataset was already examined in earlier research. A claim of survival on a truly untouched holdout is therefore unavailable; new market data are required.

**13. Direction versus risk management.** The selected model's fixed-size control has Sharpe -14.96, compared with -20.67 for its selected sizing. A higher net Sharpe can reflect lower turnover or exposure, including spending more time in cash. Controlled gross direction, cost and sizing contrasts are needed before describing any difference as alpha; volatility forecast improvement alone is risk information.

**14. Nearby settings.** The selected strategy's tested neighboring exposure/threshold settings produce holdout Sharpe from -21.57 to -17.82. This limited robustness check does not cover every train window, refit schedule or forecast horizon. No parameter is reselected using these holdout results.
