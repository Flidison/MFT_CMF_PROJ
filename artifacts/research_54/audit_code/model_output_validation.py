"""Independent model validation against a preserved historical snapshot.

Uses no forecasting helper from 03/07/08. EGARCH filters are scalar recursions;
future Gaussian offsets are a matrix convolution, independent of the production
recursive factor generator. All other forecast columns must remain unchanged.
"""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from numba import njit
from threadpoolctl import threadpool_limits

ALLOWED_FORECAST_COLUMNS=set()

def column_fingerprint(series):
    """Exact ordered-value fingerprint under the pinned pandas version."""
    header=json.dumps({'dtype':str(series.dtype),'rows':len(series)},sort_keys=True).encode()
    values=pd.util.hash_pandas_object(series,index=False).to_numpy(dtype=np.uint64).tobytes()
    return hashlib.sha256(header+values).hexdigest()

def unchanged_from_fingerprints(after,record,allowed):
    assert list(after.columns)==record['columns'] and len(after)==record['rows']
    for column in after:
        if column not in allowed:
            assert column_fingerprint(after[column])==record['fingerprints'][column],f'Unexpected forecast-column change: {column}'

def unchanged_except(before,after,allowed):
    assert list(before.columns)==list(after.columns) and before.shape==after.shape
    columns=[c for c in before if c not in allowed]
    pd.testing.assert_frame_equal(before[columns],after[columns],check_exact=True)

@njit
def reference_next_log(values,segments,location,scale,parameters):
    out=np.full(len(values),np.nan);active=False;previous=0.;log_variance=0.
    omega,alpha,beta,gamma=parameters
    for i in range(len(values)):
        if not np.isfinite(values[i]):active=False;continue
        if not active or i==0 or segments[i]!=segments[i-1]:log_variance=0.
        else:
            shock=previous*np.exp(-.5*log_variance)
            log_variance=min(30.,max(-30.,omega+beta*log_variance+alpha*(abs(shock)-np.sqrt(2/np.pi))+gamma*shock))
        previous=(values[i]-location)/scale
        shock=previous*np.exp(-.5*log_variance)
        out[i]=min(30.,max(-30.,omega+beta*log_variance+alpha*(abs(shock)-np.sqrt(2/np.pi))+gamma*shock))
        active=True
    return out

def reference_future(next_log,parameters,scale,seed,horizon=30):
    omega,alpha,beta,gamma=parameters;rng=np.random.default_rng(seed)
    # Preserve the original requested-horizon random-stream convention.
    z=rng.standard_normal((1024,horizon))
    z=np.vstack([z,-z]);innovations=omega+alpha*(abs(z)-np.sqrt(2/np.pi))+gamma*z
    offsets=np.zeros((len(z),horizon))
    for j in range(1,horizon):offsets[:,j]=innovations[:,:j]@(beta**np.arange(j-1,-1,-1))
    factors=np.exp(np.clip(offsets,-60,60)).mean(axis=0)
    return scale**2*np.exp(next_log[:,None]*(beta**np.arange(horizon)))*factors

def assert_changed_rows_only(before,after,keys,allowed):
    a=before.set_index(keys).sort_index();b=after.set_index(keys).sort_index()
    assert a.index.equals(b.index) and list(a.columns)==list(b.columns)
    permitted=np.asarray([allowed(key if isinstance(key,tuple) else (key,)) for key in a.index])
    pd.testing.assert_frame_equal(a.loc[~permitted],b.loc[~permitted],check_exact=True)

def same_number(actual,expected):
    np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-12,equal_nan=True)

def validate(root,snapshot):
    root=Path(root);snapshot=Path(snapshot);models=root/'artifacts/research_54/models';old=snapshot/'models'
    manifest=json.loads((root/'artifacts/research_54/statistics/manifest.json').read_text())
    variance=pd.read_csv(models/'variance.csv');floor_table=pd.read_csv(models/'qlike_floor_sensitivity_by_file.csv')
    files=0;forecast_rows=0;metric_rows=0;fit_files=0;max_relative=0.
    for name in sorted(p.name for p in old.glob('*.csv')):
        if name not in {'coverage.csv','variance.csv','variance_summary.csv','qlike_floor_sensitivity_by_file.csv','qlike_floor_sensitivity_summary.csv'}:
            assert (old/name).read_bytes()==(models/name).read_bytes(),f'Unexpected CSV change: {name}'
    coverage=pd.read_csv(models/'coverage.csv');unchanged_except(pd.read_csv(old/'coverage.csv'),coverage,{'forecast_sha256'})
    for number,rec in enumerate(manifest['features'],1):
        name=Path(rec['file']).stem
        a=json.loads((old/'by_file'/(name+'.json')).read_text())['results']['fits']
        fits=json.loads((models/'by_file'/(name+'.json')).read_text())['results']['fits']
        assert fits==a,f'Changed fitted coefficients: {name}';fit_files+=1
        path=models/'forecasts'/(name+'.parquet')
        if not path.exists():continue
        after=pd.read_parquet(path);previous=old/'forecasts'/path.name
        if previous.exists():
            unchanged_except(pd.read_parquet(previous),after,ALLOWED_FORECAST_COLUMNS)
        else:
            baseline=json.loads((snapshot/'compact_baseline/forecast_columns.json').read_text())
            unchanged_from_fingerprints(after,baseline['files'][path.name],ALLOWED_FORECAST_COLUMNS)
        with path.open('rb') as handle:digest=hashlib.file_digest(handle,'sha256').hexdigest()
        assert coverage.set_index('file').loc[rec['file'],'forecast_sha256']==digest
        fit=next(f for f in fits if f.get('success') and f.get('stage')=='full_train' and f.get('model')=='V2_EGARCH')
        frame=pd.read_parquet(root/rec['path']);values=frame.log_return.to_numpy();segments=frame.segment_id.to_numpy()
        indices=pd.Index(frame.ID).get_indexer(after.ID);assert (indices>=0).all()
        mu=fit['location'];scale=fit['scale'];parameters=np.array(fit['parameters'])
        log_next=reference_next_log(values,segments,mu,scale,parameters)[indices]
        with threadpool_limits(limits=1):future=reference_future(log_next,parameters,scale,42+100*number+1)
        for horizon in [1,5,30]:
            expected=future[:,:horizon].mean(axis=1);saved=after[f'variance_V2_EGARCH_h{horizon}'].to_numpy()
            np.testing.assert_allclose(saved,expected,rtol=1e-11,atol=1e-18,equal_nan=True)
            finite=np.isfinite(expected)&(expected>0)
            max_relative=max(max_relative,float(np.max(np.abs(saved[finite]/expected[finite]-1))))
            ix=indices[:,None]+np.arange(1,horizon+1);safe=np.minimum(ix,len(frame)-1)
            target=np.mean((values[safe]-mu)**2,axis=1)
            valid=(indices+horizon<len(frame))&(segments[indices]==segments[safe[:,-1]])&np.isfinite(values[safe]).all(axis=1)
            target[~valid]=np.nan
            np.testing.assert_allclose(after[f'variance_target_h{horizon}'],target,rtol=1e-11,atol=1e-18,equal_nan=True)
            if horizon==1:continue
            common=after[f'variance_common_h{horizon}'].to_numpy(bool)
            for period in ['test','2020','2021']:
                mask=common if period=='test' else common&(after.date.dt.year.to_numpy()==int(period))
                y=target[mask];raw=expected[mask];v=np.maximum(raw,scale**2*1e-8)
                baseline=np.maximum(after.loc[mask,f'variance_EWMA_h{horizon}'].to_numpy(),scale**2*1e-8)
                loss=np.log(v)+y/v;delta=loss-np.log(baseline)-y/baseline
                row=variance[(variance.file==rec['file'])&(variance.model=='V2_EGARCH')&(variance.horizon==horizon)&(variance.period==period)]
                assert len(row)==1;row=row.iloc[0]
                expected_metrics=dict(n=len(y),qlike=loss.mean(),qlike_delta_ewma=delta.mean(),mse=np.mean((y-v)**2),
                    volatility_rmse=np.sqrt(np.mean((np.sqrt(y)-np.sqrt(v))**2)),volatility_correlation=np.corrcoef(np.sqrt(y),np.sqrt(v))[0,1],
                    floor_count=int((raw<scale**2*1e-8).sum()),realized_to_forecast=y.mean()/v.mean(),min_forecast=raw.min(),max_forecast=raw.max())
                for key,value in expected_metrics.items():same_number(row[key],value)
                metric_rows+=1
        common=after.variance_common_h5.to_numpy(bool);y=after.loc[common,'variance_target_h5'].to_numpy()
        for row in floor_table[(floor_table.file==rec['file'])&(floor_table.model=='V2_EGARCH')].itertuples():
            v=np.maximum(after.loc[common,'variance_V2_EGARCH_h5'].to_numpy(),scale**2*row.floor_ratio)
            base=np.maximum(after.loc[common,'variance_EWMA_h5'].to_numpy(),scale**2*row.floor_ratio)
            same_number(row.qlike_delta_ewma,np.mean(np.log(v)+y/v-np.log(base)-y/base));assert row.n==len(y)
        files+=1;forecast_rows+=len(after)
    assert_changed_rows_only(pd.read_csv(old/'variance.csv'),variance,['file','period','model','horizon'],lambda k:False)
    summary=pd.read_csv(models/'variance_summary.csv')
    assert_changed_rows_only(pd.read_csv(old/'variance_summary.csv'),summary,['period','model','horizon'],lambda k:False)
    for row in summary[(summary.model=='V2_EGARCH')&summary.horizon.isin([5,30])].itertuples():
        q=variance[(variance.model==row.model)&(variance.period==row.period)&(variance.horizon==row.horizon)]
        for actual,expected in [(row.files,q.file.nunique()),(row.n,q.n.sum()),(row.median_qlike_delta_ewma,q.qlike_delta_ewma.median()),
            (row.mean_qlike_delta_ewma,q.qlike_delta_ewma.mean()),(row.better_files,(q.qlike_delta_ewma<0).sum()),(row.median_vol_corr,q.volatility_correlation.median()),(row.floor_count,q.floor_count.sum())]:same_number(actual,expected)
    assert_changed_rows_only(pd.read_csv(old/'qlike_floor_sensitivity_by_file.csv'),floor_table,['file','model','floor_ratio'],lambda k:False)
    floor_summary=pd.read_csv(models/'qlike_floor_sensitivity_summary.csv')
    assert_changed_rows_only(pd.read_csv(old/'qlike_floor_sensitivity_summary.csv'),floor_summary,['model','floor_ratio'],lambda k:False)
    for row in floor_summary[floor_summary.model=='V2_EGARCH'].itertuples():
        q=floor_table[(floor_table.model==row.model)&(floor_table.floor_ratio==row.floor_ratio)]
        for actual,expected in [(row.files,q.file.nunique()),(row.median_delta,q.qlike_delta_ewma.median()),(row.mean_delta,q.qlike_delta_ewma.mean()),(row.floor_hits,q.floor_count.sum())]:same_number(actual,expected)
    result=dict(status='passed',forecast_files=files,forecast_rows=forecast_rows,fit_files_exactly_unchanged=fit_files,
        independently_recomputed_metric_rows=metric_rows,max_relative_forecast_error=max_relative,
        allowed_forecast_columns=sorted(ALLOWED_FORECAST_COLUMNS),other_forecasts_exactly_unchanged=True,
        target_windows_rebuilt_from_features=[1,5,30],csv_changes_restricted_and_recomputed=True)
    (root/'artifacts/research_54/audit_evidence/pre_handoff_model_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
