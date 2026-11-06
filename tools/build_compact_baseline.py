"""Build public verification records from an existing complete historical snapshot.

This never derives historical fingerprints from current forecasts. The full
historical input files must exist. Existing historical data are read-only.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    with path.open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',required=True,type=Path,help='Complete preserved historical snapshot')
    parser.add_argument('--output',required=True,type=Path,help='New empty output directory outside that snapshot')
    args=parser.parse_args();SNAP=args.snapshot.resolve();OUT=args.output.resolve()
    if OUT.is_relative_to(SNAP):parser.error('Output must be outside the historical snapshot')
    if OUT.exists() and any(OUT.iterdir()):raise FileExistsError('Use a new or empty output directory')
    spec=importlib.util.spec_from_file_location('model_validation',ROOT/'artifacts/research_54/audit_code/model_output_validation.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    (OUT/'common_masks').mkdir(parents=True,exist_ok=True)
    forecasts={'method':'pandas ordered-value hashes + dtype/row-count header, SHA-256','pandas':pd.__version__,'files':{}}
    for source in sorted((SNAP/'models/forecasts').glob('*.parquet')):
        frame=pd.read_parquet(source)
        forecasts['files'][source.name]=dict(source_sha256=sha(source),rows=len(frame),columns=list(frame.columns),
            fingerprints={column:module.column_fingerprint(frame[column]) for column in frame})
    assert len(forecasts['files'])==53,'Complete historical forecast inputs are required'
    masks={'files':{}}
    for source in sorted((SNAP/'backtest/decisions').glob('*.parquet')):
        frame=pd.read_parquet(source,columns=['ID','common_at_signal'])
        target=OUT/'common_masks'/source.name
        frame.to_parquet(target,index=False,compression='zstd')
        masks['files'][source.name]=dict(source_sha256=sha(source),compact_sha256=sha(target),rows=len(frame))
    assert len(masks['files'])==54,'Complete historical decision inputs are required'
    notebooks={name:dict(sha256=sha(SNAP/name),bytes=(SNAP/name).stat().st_size)
        for name in ['07_forecasting_models_54.ipynb','08_backtest_fees_risk_54.ipynb']}
    for name,data in [('forecast_columns',forecasts),('decision_masks',masks),('source_notebooks',notebooks)]:
        (OUT/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
    print('Created 53 forecast fingerprints and 54 exact historical common masks.')

if __name__=='__main__':main()
