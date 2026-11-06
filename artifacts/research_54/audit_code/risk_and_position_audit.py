"""Independently validate all three08 risk forecasts and executed position sizes.

Uses independent reconstruction from training_normalization_audit, not07/08 code.
EGARCH Monte Carlo is regenerated for the actual six-step08 forecast horizon.
"""
from pathlib import Path
import importlib.util,json
import numpy as np
import pandas as pd
ROOT=Path.cwd();OUT=ROOT/'artifacts/research_54';C=OUT/'audit_code';B=OUT/'backtest'
def main():
    spec=importlib.util.spec_from_file_location('independent_training_reconstruction',C/'training_normalization_audit.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    manifest=json.loads((OUT/'statistics/manifest.json').read_text())
    models=['V1_GARCH','V2_EGARCH','V3_GJR_GARCH'];registry=pd.read_csv(B/'strategy_registry.csv').set_index('strategy')
    rows=[]
    for number,record in enumerate(manifest['features'],1):
        file=record['file'];stem=Path(file).stem
        frame=pd.read_parquet(ROOT/record['path'],columns=['ID','log_return','segment_id'])
        dec=pd.read_parquet(B/'decisions'/f'{stem}.parquet')
        ix=pd.Index(frame.ID).get_indexer(dec.ID);assert (ix>=0).all()
        fits=json.loads((OUT/'models/by_file'/f'{stem}.json').read_text())['results']['fits']
        if file=='SA9999.XZCE.csv':fits=json.loads((B/'sa_short_history_fits.json').read_text())
        r=frame.log_return.to_numpy();seg=frame.segment_id.to_numpy()
        for j,model in enumerate(models):
            fit=next(f for f in fits if f['stage']=='full_train' and f['model']==model and f['success'])
            _,expected,_,_=helper.reconstruct_volatility(r,seg,fit,42+100*number+j)
            actual=dec['variance_H_'+model].to_numpy();want=expected[ix]
            np.testing.assert_allclose(actual,want,rtol=1e-11,atol=1e-18,equal_nan=True)
            rows.append(dict(file=file,check=model+'_delayed_risk',n=int(np.isfinite(actual).sum()),max_absolute_error=float(np.nanmax(np.abs(actual-want)))))
        trades=pd.read_parquet(B/'trades'/f'{stem}.parquet',columns=['strategy','cohort','signal_ID','position'])
        index=pd.Index(dec.ID)
        for (strategy,cohort),t in trades.groupby(['strategy','cohort'],sort=False):
            cfg=registry.loc[strategy];select=index.get_indexer(t.signal_ID);assert (select>=0).all()
            source=dec.iloc[select];raw=source[cfg.direction].to_numpy()
            score=2*raw-1 if cfg.direction.startswith('D3_') else np.sign(raw)
            assert np.isfinite(score).all()
            if cfg.volatility!='Fixed':
                var=source['variance_H_'+cfg.volatility].to_numpy();assert (np.isfinite(var)&(var>0)).all()
                score=score*.001/np.sqrt(np.maximum(var,1e-10))
            if pd.notna(cfg.expansion):assert (source['expansion_'+cfg.expansion]>=1.2).all()
            assert source.clock_permitted.all() and source.volume.gt(0).all() and source.close.gt(0).all()
            if cohort=='common':assert source.common_at_signal.all()
            expected=np.clip(score,-3.,3.)*cfg.multiplier
            np.testing.assert_allclose(expected,t.position,rtol=1e-12,atol=1e-14)
            rows.append(dict(file=file,check=strategy+'__'+cohort+'_position',n=len(t),max_absolute_error=float(np.max(np.abs(expected-t.position)))))
        if number%9==0:print(f'Independent risk/position validation {number}/54',flush=True)
    pd.DataFrame(rows).to_csv(OUT/'audit_risk_and_position_checks.csv',index=False)
    summary=dict(checks=len(rows),risk_forecasts=54*3,position_rows_checked=sum(x['n'] for x in rows if x['check'].endswith('_position')),
        max_absolute_error=max(x['max_absolute_error'] for x in rows),status='passed',
        egarch_note='08 uses six-step simulation with its fixed seed; 07 standalone scoring uses30-step simulation. Parameters match; Monte Carlo paths are horizon-dependent, so raw07 variance_h5 must not replace08 delayed risk.')
    (OUT/'audit_risk_and_position_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
