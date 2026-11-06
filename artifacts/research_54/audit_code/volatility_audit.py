"""Independent, read-only forecast audit. Run from project root with venv/bin/python.

Uses saved forecasts and source features, not Notebook07 metric functions. No refit.
QLIKE = log(max(forecast, floor)) + realized_variance/max(forecast, floor).
Metrics are predictive diagnostics; target-valid masks must never enter trading decisions.
"""
from pathlib import Path
import ast
import hashlib
import json
import numpy as np
import pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'artifacts/research_54'
MODELS = OUT / 'models'
CODE = OUT / 'audit_code'
MODEL_NAMES = ['EWMA', 'V1_GARCH', 'V3_GJR_GARCH', 'V2_EGARCH']
DIRECTIONS = ['D0_Momentum5','D1_Raw_ARMA','D2_GARCH_ARMA','D2_EGARCH_ARMA',
              'D2_GJR_ARMA','D3_Logistic_Core','D3_Logistic_Asymmetric']
FLOOR_RATIO = 1e-8

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def corr(x, y):
    return float(np.corrcoef(x,y)[0,1]) if len(x)>1 and np.ptp(x)>0 and np.ptp(y)>0 else np.nan

@njit
def independent_symmetric_recursion(r, seg, mu, scale, omega, positive, negative, beta):
    """Scalar filter written independently; conditional h[t] uses only r[:t]."""
    result = np.full((len(r),4), np.nan)
    h = 1.0
    prev = 0.0
    active = False
    persistence = beta + (positive+negative)/2
    for i in range(len(r)):
        if not np.isfinite(r[i]):
            active = False
            continue
        fresh = i==0 or not active or seg[i]!=seg[i-1]
        if fresh:
            h=1.0
        else:
            h=omega+beta*h+(negative if prev<0 else positive)*prev*prev
        x=(r[i]-mu)/scale
        nxt=omega+beta*h+(negative if x<0 else positive)*x*x
        total=0.0
        for horizon in range(1,31):
            total+=nxt
            if horizon==1: result[i,0]=total*scale*scale
            if horizon==5: result[i,1]=total*scale*scale/5
            if horizon==30: result[i,2]=total*scale*scale/30
            if horizon==6: result[i,3]=total*scale*scale-result[i,0]
            nxt=omega+persistence*nxt
        prev=x
        active=True
    return result

@njit
def independent_ewma(r,seg,mu,var):
    result=np.full(len(r),np.nan)
    h=var
    active=False
    for i in range(len(r)):
        if not np.isfinite(r[i]):
            active=False
            continue
        if i==0 or not active or seg[i]!=seg[i-1]: h=var
        h=.94*h+.06*(r[i]-mu)**2
        result[i]=h
        active=True
    return result

def delayed_variance_rows(file,feature,eligible07,checks):
    """Score the planned08 holding window, never using execution outcomes as masks."""
    stem=Path(file).stem
    dec=pd.read_parquet(OUT/'backtest/decisions'/f'{stem}.parquet',columns=['ID','date','variance_H_V1_GARCH','variance_H_V3_GJR_GARCH'])
    pos=feature.set_index('ID').index.get_indexer(dec.ID)
    assert (pos>=0).all()
    np.testing.assert_array_equal(feature.date.iloc[pos].to_numpy(),dec.date.to_numpy())
    r=feature.log_return.to_numpy();seg=feature.segment_id.to_numpy();close=feature.close.to_numpy()
    train=feature.date.lt('2020-01-01').to_numpy(); mu=np.nanmean(r[train]);var=np.nanvar(r[train]);floor=FLOOR_RATIO*var
    predictions={'EWMA':independent_ewma(r,seg,mu,var)[pos],
        'V1_GARCH':dec.variance_H_V1_GARCH.to_numpy()/5,
        'V3_GJR_GARCH':dec.variance_H_V3_GJR_GARCH.to_numpy()/5}
    if not eligible07:
        extension=json.loads((OUT/'backtest/sa_short_history_fits.json').read_text())
        for model in ['V1_GARCH','V3_GJR_GARCH']:
            fit=next(f for f in extension if f['model']==model)
            np.testing.assert_allclose([fit['location'],fit['scale']],[mu,np.sqrt(var)],rtol=1e-12,atol=1e-15)
            expected=independent_symmetric_recursion(r,seg,fit['location'],fit['scale'],*fit['parameters'])[pos,3]/5
            np.testing.assert_allclose(expected,predictions[model],rtol=1e-11,atol=1e-18,equal_nan=True)
            checks.append(dict(file=file,check=f'08 extension independent {model} delayed-risk',max_abs_error=float(np.nanmax(np.abs(expected-predictions[model])))))
    target=np.full(len(pos),np.nan); within=pos+6<len(r);ix=pos[within];good=seg[ix]==seg[ix+6];total=np.zeros(len(ix))
    for step in range(1,7):
        good &= np.isfinite(r[ix+step])
        if step>=2:total+=(r[ix+step]-mu)**2
    good &= np.isfinite(close[ix+1])&np.isfinite(close[ix+6])&(close[ix+1]>0)&(close[ix+6]>0)
    target[np.flatnonzero(within)[good]]=total[good]/5
    common=np.isfinite(target)
    for pred in predictions.values():common &= np.isfinite(pred)&(pred>=0)
    cohorts=['delayed_h5_08_extended54']+(['delayed_h5_07_eligible53'] if eligible07 else [])
    rows=[]
    for cohort in cohorts:
        for period in ['test','2020','2021']:
            period_origins=np.ones(len(dec),dtype=bool) if period=='test' else dec.date.dt.year.eq(int(period)).to_numpy()
            use=common&period_origins;y=target[use];baseline=np.maximum(predictions['EWMA'][use],floor);base=np.log(baseline)+y/baseline
            for model,forecast in predictions.items():
                raw=forecast[use];v=np.maximum(raw,floor);loss=np.log(v)+y/v
                rows.append(dict(row_type='instrument',file=file,period=period,horizon=5,forecast_delay_minutes=1,cohort=cohort,model=model,n=len(y),
                    available_forecast_origins=int((np.isfinite(forecast)&period_origins).sum()),all_origins=int(period_origins.sum()),
                    qlike=float(loss.mean()),qlike_delta_ewma=float((loss-base).mean()),volatility_correlation=corr(np.sqrt(y),np.sqrt(v)),
                    volatility_rmse=float(np.sqrt(np.mean((np.sqrt(y)-np.sqrt(v))**2))),floor_ratio=FLOOR_RATIO,floor_value=floor,floor_hits=int((raw<floor).sum()),
                    coverage_status='07 eligible' if eligible07 else '08 short-history extension:19 train dates',
                    window_definition='mean squared demeaned returns t+2..t+6; planned holding window; no execution filter'))
    return rows

def main():
    source=json.loads((OUT/'statistics/manifest.json').read_text())
    model_manifest=json.loads((MODELS/'manifest.json').read_text())
    notebook=json.loads((ROOT/'07_forecasting_models_54.ipynb').read_text())
    function_sources=[]
    for cell in notebook['cells']:
        if cell['cell_type']!='code': continue
        text=''.join(cell['source']); lines=text.splitlines(keepends=True)
        for node in ast.parse(text).body:
            if isinstance(node,ast.FunctionDef) and node.name.startswith(('model_','wf_','garch_parameters')):
                start=min([node.lineno,*[d.lineno for d in node.decorator_list]])-1
                function_sources.append(''.join(lines[start:node.end_lineno]).rstrip('\n')+'\n')
    code_hash=hashlib.sha256('\n'.join(function_sources).encode()).hexdigest()
    assert code_hash==model_manifest['config']['code_hash']
    assert sha(OUT/'statistics/manifest.json')==model_manifest['input_sha256']
    rows=[]; checks=[]; lineage=[]; return_rows=[]
    fits=pd.read_csv(MODELS/'fits.csv')
    numerics=pd.read_csv(MODELS/'numerics.csv')
    old_metrics=pd.read_csv(MODELS/'variance.csv')
    for number,record in enumerate(source['features'],1):
        file=record['file']; stem=Path(file).stem
        cache=json.loads((MODELS/'by_file'/f'{stem}.json').read_text())
        expected=hashlib.sha256(json.dumps(dict(config=model_manifest['config'],record=record),sort_keys=True).encode()).hexdigest()
        assert cache['fingerprint']==expected, file
        assert sha(ROOT/record['path'])==record['sha256'], file
        cov=cache['results']['coverage'][0]
        feature=pd.read_parquet(ROOT/record['path'],columns=['date','ID','segment_id','log_return','close'])
        r=feature.log_return.to_numpy(); seg=feature.segment_id.to_numpy(); dates=feature.date
        test=dates.ge('2020-01-01').to_numpy(); train=~test
        for period,select in [('test',test),('train',train)]:
            rr=r[select]; ss=seg[select]; finite=rr[np.isfinite(rr)]
            valid=(ss[1:]==ss[:-1])&np.isfinite(rr[1:])&np.isfinite(rr[:-1])
            sd=finite.std(ddof=1); mu=finite.mean()
            return_row=dict(file=file,period=period,n=len(finite),return_acf1=corr(rr[1:][valid],rr[:-1][valid]),
                abs_return_acf1=corr(np.abs(rr[1:][valid]),np.abs(rr[:-1][valid])),
                excess_kurtosis=float(pd.Series(finite).kurt()),
                tail_3sigma_probability=float(np.mean(np.abs(finite-mu)>3*sd)))
            for lag in [5,10,30]:
                allowed=(ss[lag:]==ss[:-lag])&np.isfinite(rr[lag:])&np.isfinite(rr[:-lag])
                return_row[f'abs_return_acf{lag}']=corr(np.abs(rr[lag:][allowed]),np.abs(rr[:-lag][allowed]))
            return_rows.append(return_row)
        rows.extend(delayed_variance_rows(file,feature,bool(cov.get('forecast_sha256')),checks))
        if not cov.get('forecast_sha256'):
            lineage.append(dict(file=file,status=cov['status'],forecast_file=False,model_fingerprint_verified=True,
                train_dates=cov['train_dates'],reason='07 minimum 20 train dates; SA has 19. 08 extension is separately fitted.'))
            for model in MODEL_NAMES:
                rows.append(dict(row_type='unavailable',file=file,period='test',horizon=5,cohort='common_GARCH_GJR_EWMA',
                    model=model,n=0,coverage_status=cov['status'],floor_ratio=FLOOR_RATIO))
            continue
        path=MODELS/'forecasts'/f'{stem}.parquet'
        assert sha(path)==cov['forecast_sha256']
        pred=pd.read_parquet(path)
        pos=feature.set_index('ID').index.get_indexer(pred.ID)
        assert (pos>=0).all()
        np.testing.assert_array_equal(feature.date.iloc[pos].to_numpy(),pred.date.to_numpy())
        assert pred.date.ge('2020-01-01').all()
        assert ((pred.date.dt.hour*60+pred.date.dt.minute)%6==0).all()
        stage_fits=cache['results']['fits']
        assert all(pd.Timestamp(f['train_end'])<pd.Timestamp('2020-01-01') for f in stage_fits)
        mu=float(np.nanmean(r[train])); variance=float(np.nanvar(r[train])); floor=FLOOR_RATIO*variance
        for fit in stage_fits:
            if fit['stage']=='full_train' and fit.get('success'):
                np.testing.assert_allclose([fit['location'],fit['scale']],[mu,np.sqrt(variance)],rtol=1e-12,atol=1e-15)
                checks.append(dict(file=file,check=f"full-train normalization {fit['model']}",
                    max_abs_error=float(max(abs(fit['location']-mu),abs(fit['scale']-np.sqrt(variance))))))
        np.testing.assert_allclose(pred.variance_Historical_h5,variance,rtol=1e-12)
        ewma=independent_ewma(r,seg,mu,variance)[pos]
        np.testing.assert_allclose(ewma,pred.variance_EWMA_h5,rtol=1e-11,atol=1e-18,equal_nan=True)
        checks.append(dict(file=file,check='EWMA scalar recursion',max_abs_error=float(np.nanmax(np.abs(ewma-pred.variance_EWMA_h5)))))
        decision_risk=pd.read_parquet(OUT/'backtest/decisions'/f'{stem}.parquet',columns=['ID','date','variance_H_V1_GARCH','variance_H_V3_GJR_GARCH'])
        np.testing.assert_array_equal(decision_risk.ID,pred.ID)
        for model in ['V1_GARCH','V3_GJR_GARCH']:
            fit=next(f for f in stage_fits if f['stage']=='full_train' and f['model']==model)
            z=independent_symmetric_recursion(r,seg,fit['location'],fit['scale'],*fit['parameters'])[pos]
            for j,h in enumerate([1,5,30]):
                actual=pred[f'variance_{model}_h{h}'].to_numpy()
                np.testing.assert_allclose(z[:,j],actual,rtol=1e-11,atol=1e-18,equal_nan=True)
                checks.append(dict(file=file,check=f'{model} scalar recursion h{h}',max_abs_error=float(np.nanmax(np.abs(z[:,j]-actual)))))
            actual08=decision_risk['variance_H_'+model].to_numpy()
            np.testing.assert_allclose(z[:,3],actual08,rtol=1e-11,atol=1e-18,equal_nan=True)
            checks.append(dict(file=file,check=f'08 {model} delayed five-minute risk: sum t+2..t+6',max_abs_error=float(np.nanmax(np.abs(z[:,3]-actual08)))))
        close=feature.close.to_numpy()
        delayed=np.full(len(pos),np.nan); within=pos+6<len(r); ix=pos[within]
        valid=seg[ix]==seg[ix+6]
        for step in range(1,7): valid &= np.isfinite(r[ix+step])
        valid &= np.isfinite(close[ix+1])&np.isfinite(close[ix+6])&(close[ix+1]>0)&(close[ix+6]>0)
        delayed[np.flatnonzero(within)[valid]]=np.log(close[ix[valid]+6]/close[ix[valid]+1])
        np.testing.assert_allclose(delayed,pred.direction_target_h5_delay1,rtol=1e-12,atol=1e-18,equal_nan=True)
        checks.append(dict(file=file,check='direction target log(C[t+6]/C[t+1])',max_abs_error=float(np.nanmax(np.abs(delayed-pred.direction_target_h5_delay1)))))
        for h in [1,5,30]:
            # Endpoint segment identity ensures uninterrupted one-minute source segments.
            actual=np.full(len(pos),np.nan); good=pos+h<len(r); ix=pos[good]
            valid=seg[ix]==seg[ix+h]
            total=np.zeros(len(ix))
            for step in range(1,h+1):
                valid &= np.isfinite(r[ix+step]); total+=(r[ix+step]-mu)**2
            valid &= np.isfinite(close[ix])&np.isfinite(close[ix+h])&(close[ix]>0)&(close[ix+h]>0)
            where=np.flatnonzero(good)[valid]; actual[where]=total[valid]/h
            np.testing.assert_allclose(actual,pred[f'variance_target_h{h}'],rtol=1e-12,atol=1e-18,equal_nan=True)
            checks.append(dict(file=file,check=f'independent realized target h{h}',max_abs_error=float(np.nanmax(np.abs(actual-pred[f'variance_target_h{h}'])))))
            forecast={m:pred[f'variance_{m}_h{h}'].to_numpy() for m in MODEL_NAMES}
            common=np.isfinite(actual)&np.isfinite(pred.log_return.to_numpy())
            for m in ['EWMA','V1_GARCH','V3_GJR_GARCH']: common &= np.isfinite(forecast[m])&(forecast[m]>=0)
            original=common.copy()
            for m in ['Historical','Trailing30','V2_EGARCH']:
                v=pred[f'variance_{m}_h{h}'].to_numpy(); original &= np.isfinite(v)&(v>=0)
            np.testing.assert_array_equal(original,pred[f'variance_common_h{h}'].to_numpy())
            for cohort,mask in [('common_GARCH_GJR_EWMA',common),('original_common_all6',original)]:
                for period in ['test','2020','2021']:
                    period_origins=np.ones(len(pred),dtype=bool) if period=='test' else pred.date.dt.year.eq(int(period)).to_numpy()
                    use=mask&period_origins
                    y=actual[use]; baseline=np.maximum(forecast['EWMA'][use],floor)
                    if not len(y): continue
                    base_loss=np.log(baseline)+y/baseline
                    for model in MODEL_NAMES:
                        raw=forecast[model][use]
                        assert np.isfinite(raw).all()
                        v=np.maximum(raw,floor); loss=np.log(v)+y/v
                        rows.append(dict(row_type='instrument',file=file,period=period,horizon=h,cohort=cohort,model=model,
                            n=len(y),available_forecast_origins=int((np.isfinite(forecast[model])&period_origins).sum()),
                            all_origins=int(period_origins.sum()),qlike=float(loss.mean()),qlike_delta_ewma=float((loss-base_loss).mean()),
                            volatility_correlation=corr(np.sqrt(y),np.sqrt(v)),volatility_rmse=float(np.sqrt(np.mean((np.sqrt(y)-np.sqrt(v))**2))),
                            floor_ratio=FLOOR_RATIO,floor_value=floor,floor_hits=int((raw<floor).sum()),coverage_status='available'))
        decision_path=OUT/'backtest/decisions'/f'{stem}.parquet'
        dec=pd.read_parquet(decision_path,columns=['ID','date',*DIRECTIONS])
        merged=pred[['ID','date',*DIRECTIONS]].merge(dec,on=['ID','date'],suffixes=('_07','_08'),validate='one_to_one')
        assert len(merged)==len(pred)==len(dec)
        for d in DIRECTIONS:
            x=merged[d+'_07'].to_numpy(); y=merged[d+'_08'].to_numpy()
            np.testing.assert_allclose(x,y,rtol=1e-12,atol=1e-15,equal_nan=True)
            checks.append(dict(file=file,check=f'07 to 08 {d}',max_abs_error=float(np.nanmax(np.abs(x-y))) if np.isfinite(x-y).any() else np.nan))
        lineage.append(dict(file=file,status=cov['status'],forecast_file=True,model_fingerprint_verified=True,
            forecast_hash_verified=True,train_dates=cov['train_dates'],inner_status=cov.get('inner_status'),
            direction_models_available=cov.get('direction_models_available'),origins=len(pred),
            reason='' if cov.get('inner_status')=='eligible' else 'Insufficient pre-2019 training history for composite models.'))
        if number%9==0: print(f'{number}/54 forecast audits complete',flush=True)
    result=pd.DataFrame(rows)
    result['forecast_delay_minutes']=result.forecast_delay_minutes.fillna(0).astype(int)
    instruments=result[result.row_type.eq('instrument')]
    summaries=[]
    for key,group in instruments.groupby(['period','horizon','cohort','model'],sort=False):
        period,horizon,cohort,model=key
        summaries.append(dict(row_type='equal_file_summary',file='ALL_AVAILABLE',period=period,horizon=horizon,cohort=cohort,model=model,
            forecast_delay_minutes=int(group.forecast_delay_minutes.iloc[0]),
            n=int(group.n.sum()),instruments=group.file.nunique(),qlike=float(group.qlike.mean()),
            qlike_delta_ewma=float(group.qlike_delta_ewma.mean()),median_qlike_delta_ewma=float(group.qlike_delta_ewma.median()),
            volatility_correlation=float(group.volatility_correlation.median()),floor_ratio=FLOOR_RATIO,
            floor_hits=int(group.floor_hits.sum()),better_than_ewma_instruments=int(group.qlike_delta_ewma.lt(0).sum()),
            aggregation='QLIKE: equal-file mean; correlation: file median; n: summed observations'))
    result=pd.concat([result,pd.DataFrame(summaries)],ignore_index=True)
    result.to_csv(OUT/'volatility_model_comparison.csv',index=False)
    comparison=instruments.query('cohort=="original_common_all6"').merge(old_metrics,on=['file','period','horizon','model'],suffixes=('_audit','_07'))
    np.testing.assert_array_equal(comparison.n_audit,comparison.n_07)
    discrepancies={}
    for column in ['qlike','qlike_delta_ewma','volatility_correlation','volatility_rmse']:
        error=float(np.max(np.abs(comparison[column+'_audit']-comparison[column+'_07'])))
        discrepancies[column]=error
        np.testing.assert_allclose(comparison[column+'_audit'],comparison[column+'_07'],rtol=1e-10,atol=1e-12)
    improved=[]
    for (period,horizon,cohort),group in instruments.groupby(['period','horizon','cohort']):
        q=group.pivot(index='file',columns='model',values='qlike')
        improved.append(dict(period=period,horizon=horizon,cohort=cohort,files=len(q),
            gjr_better_than_garch=int((q.V3_GJR_GARCH<q.V1_GARCH).sum()),
            fraction_gjr_better_than_garch=float((q.V3_GJR_GARCH<q.V1_GARCH).mean()),
            median_gjr_minus_garch=float((q.V3_GJR_GARCH-q.V1_GARCH).median())))
    pd.DataFrame(checks).to_csv(CODE/'forecast_independent_checks.csv',index=False)
    pd.DataFrame(lineage).to_csv(CODE/'forecast_lineage_and_coverage.csv',index=False)
    pd.DataFrame(improved).to_csv(CODE/'gjr_pairwise_comparison.csv',index=False)
    ret=pd.DataFrame(return_rows); ret.to_csv(CODE/'return_properties_independent.csv',index=False)
    test=ret[ret.period.eq('test')]
    old_acf=pd.read_csv(OUT/'statistics/acf.csv')
    old_tails=pd.read_csv(OUT/'statistics/tails.csv')
    for series,col in [('log_return','return_acf1'),('abs_log_return','abs_return_acf1')]:
        q=old_acf.query('series==@series and sample=="all" and lag==1').merge(ret,on=['file','period'])
        np.testing.assert_allclose(q.acf,q[col],atol=1e-12)
    for lag in [5,10,30]:
        q=old_acf.query('series=="abs_log_return" and sample=="all" and lag==@lag').merge(ret,on=['file','period'])
        np.testing.assert_allclose(q.acf,q[f'abs_return_acf{lag}'],atol=1e-12)
    q=old_tails.query('return_type=="log_return" and volume_group=="all"').merge(ret,on=['file','period'],suffixes=('_05','_audit'))
    np.testing.assert_allclose(q.excess_kurtosis_05,q.excess_kurtosis_audit,rtol=1e-12,atol=1e-12)
    vfits=fits[fits.model.isin(MODEL_NAMES)]
    fit_summary=vfits.groupby(['stage','model']).agg(requested=('file','size'),successful=('success','sum'),boundary=('boundary',lambda s:s.eq(True).sum())).reset_index()
    fit_summary.to_csv(CODE/'volatility_fit_diagnostics.csv',index=False)
    numeric_summary=numerics.groupby(['stage','model'])[['filter_guard_hits','next_guard_hits','nonfinite_forecasts']].sum().reset_index()
    numeric_summary.to_csv(CODE/'volatility_numerical_diagnostics.csv',index=False)
    g=vfits.query('stage=="full_train" and model=="V3_GJR_GARCH"')
    findings=dict(status='independent checks passed',source_code_hash=code_hash,source_functions=len(function_sources),
        requested_files=54,notebook07_forecast_files=53,composite_files=46,
        variance_metric_reconciliation_max_abs=discrepancies,
        forecast_checks_max_abs=float(pd.DataFrame(checks).max_abs_error.max()),
        test_return_properties=dict(files=54,median_return_acf1=float(test.return_acf1.median()),
            median_abs_return_acf1=float(test.abs_return_acf1.median()),median_excess_kurtosis=float(test.excess_kurtosis.median()),
            heavier_than_gaussian_files=int(((test.excess_kurtosis>0)&(test.tail_3sigma_probability>0.0026997960632601913)).sum())),
        full_train_gjr_asymmetry=dict(negative_shock_loading_larger=int(g.gamma.gt(0).sum()),positive_shock_loading_larger=int(g.gamma.lt(0).sum()),
            median_gamma=float(g.gamma.median()),interpretation='Descriptive fitted coefficients only; no coefficient significance test or universal leverage-effect claim.'),
        h5_summary=[s for s in summaries if s['horizon']==5],
        gjr_pairwise_h5=[s for s in improved if s['horizon']==5],
        fit_summary=fit_summary.to_dict('records'),numerics=numeric_summary.to_dict('records'),
        limitations=['07 volatility metrics use t+1..t+h;08 sizes on t+2..t+6 for delayed entry. Supplementary delayed_h5 cohorts score the planned08 holding window, with53-file07-eligible and54-file08-extension groups separately. Actual delayed exits beyond5min are not a fixed forecast horizon.',
            '08 short-history SA standalone extension uses19 train dates, outside07 minimum20; must remain explicitly labelled.',
            'Boundary fits are retained, no model selected using test metrics; EGARCH guards affect train-and-test filter path counts.',
            '07 composite risk features are2016-2018 fits;08 risk sizing uses2016-2019 fits. Intentional different purposes, not interchangeable forecasts.',
            'Direction labels exclude unavailable future targets for scoring only;08 importsforecastwhitelist without targets/masks.'])
    findings['cohort_sensitivity']='Original common-all6 excludes origins lacking30-minute trailing volatility. Requested GARCH/GJR/EWMA common mask retains those origins. Both are reported; median ranking changes while equal-file mean GARCH/GJR QLIKE remains worse than EWMA. No cohort chosen on profitability.'
    (CODE/'volatility_findings.json').write_text(json.dumps(findings,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(findings,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
