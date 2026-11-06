# MFT futures research

Minute futures data: data quality, statistical dependence, direction and volatility
forecasts, and exploratory trading strategies. Research code is contained in the
notebooks; generated datasets and result files are kept locally.

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

## Research conventions

Returns, lags and model states restart at contract changes and discontinuous
minute intervals. The 54-product study trains on 2016–2019 and evaluates on
2020–18 October 2021. Universe selection is retrospective, and the historical
sample has already informed research decisions.

The fee backtest applies August 2026 exchange-fee assumptions to 2020–2021. Minute
close fills and fractional contract quantities are modelling assumptions; broker
fees, spread, impact and capacity are excluded from the baseline. None of the
47 strategy variants has a positive net return under that scenario.
