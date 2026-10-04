# MFT futures research

A sequential, three-notebook research pipeline for minute futures data: data quality, statistical feature research, and directional and volatility forecasting with exploratory trading tests. All project-owned research implementation is contained in the notebooks.

## Notebooks

Run these from the repository root, in order, using separate clean Python kernels:

1. [01_data_quality_check.ipynb](01_data_quality_check.ipynb) validates the 77 raw market files, reports data issues, and produces `artifacts/clean_market_data.parquet`.
2. [02_research_statistics_features.ipynb](02_research_statistics_features.ipynb) builds segment-aware features, descriptive statistics, correlations and significance screens. It produces `artifacts/research_features.parquet` and `artifacts/significant_combinations.csv`.
3. [03_strategies_hypotheses.ipynb](03_strategies_hypotheses.ipynb) tests momentum and reversal hypotheses, ARMA direction forecasts, logistic direction probabilities, and GARCH, EGARCH and GJR volatility forecasts. It preserves the earlier research and adds walk-forward strategy comparisons.

Saved cell outputs, result tables and figures are included. No local research helper modules are required.

## Setup

The executed environment used Python 3.11. Install the recorded dependencies and register a kernel for your notebook editor:

```bash
python3.11 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m ipykernel install --user --name mft-research --display-name "MFT research"
```

Open the notebooks in a Jupyter-compatible editor, select the `MFT research` kernel, and run from the repository root. JupyterLab can optionally be installed with `python -m pip install jupyterlab`.

## Restore the complete data snapshot

The full research snapshot is roughly 13 GiB before archive compression. Raw CSVs and Parquet datasets exceed practical Git repository limits, so they are published as independent `.tar.gz` assets in the [research snapshot release](https://github.com/Flidison/MFT_CMF_PROJ/releases/tag/research-snapshot-v1). CSV result tables, figures, notebooks and non-cache metadata are tracked directly in Git. The release also preserves the fitted-model cache so existing results can be inspected without refitting everything.

After cloning, use the GitHub CLI to download the assets and extract them from the repository root:

```bash
mkdir -p release-assets
gh release download research-snapshot-v1 \
  --repo Flidison/MFT_CMF_PROJ \
  --dir release-assets --pattern '*.tar.gz' --pattern 'SHA256SUMS'
(cd release-assets && shasum -a 256 -c SHA256SUMS)
for archive in release-assets/*.tar.gz; do
  tar -xzf "$archive"
done
```

The release files can also be downloaded through the browser. Each archive restores repository-relative paths; the archives are independent, not split byte streams. `publication_manifest.csv` lists every original research file, its SHA-256 checksum, and whether it is stored in Git or in a release archive. `release_manifest.json` records archive contents and checksums.

To rerun the complete pipeline from raw inputs, download and extract only the `raw-data-*.tar.gz` assets and run notebooks 1, 2 and 3. For the complete saved state, extract every archive. Notebook 1 defaults to `fut_data/`; its configuration cell can point to another raw data directory. The generated outputs can be recreated by running the notebooks sequentially.

The local virtual environment, operating-system files and interpreter caches are excluded from publication. Original market data, generated datasets, research results and model-output caches are preserved.

## Main research conventions and findings

- One-minute bars, with returns, lags and rolling calculations confined to continuous segments and delivery contracts.
- Separate direction and conditional-volatility forecasting layers.
- Five-minute holding horizon, next-valid-close execution, and a main transaction cost assumption of 1 basis point per side of notional turnover.
- Training-only model selection, historical walk-forward refits, validation in 2018–2019 and a locked evaluation period in 2020–2021. The historical sample had already been explored, so this is not a pristine untouched holdout.
- Directional accuracy is close to chance. GARCH volatility forecasting is more informative than the directional forecasts. EGARCH instability is retained and flagged.
- All ten principal combined strategies have negative net performance at the main cost assumption. Statistical dependence does not establish a production-ready profitable strategy.

See [strategy performance](artifacts/strategies/two_layer_walk_forward/strategy_performance.csv), [research conclusions](artifacts/strategies/two_layer_walk_forward/research_conclusions.md), and the executed third notebook for the complete evidence and limitations.
