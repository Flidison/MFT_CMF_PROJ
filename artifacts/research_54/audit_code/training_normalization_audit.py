"""Reconstruct 2019 predictors independently and reconcile fitted normalization.

No optimizer or Notebook07 computational function is called. Forecast parameters
are fixed cached 2016--2018 estimates; the training design matrix is reconstructed
from the source returns, then its moments are compared with stored fit moments.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from numba import njit

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'artifacts/research_54'
CODE=OUT/'audit_code'
MODELS=['V1_GARCH','V2_EGARCH','V3_GJR_GARCH']

@njit
def conditional_variance(r,seg,mu,scale,p,kind):
    out=np.full(len(r),np.nan); h=1.; previous=0.; active=False
    for i in range(len(r)):
        if not np.isfinite(r[i]): active=False;continue
        fresh=i==0 or not active or seg[i]!=seg[i-1]
        if fresh: h=1.
        elif kind==1:
            z=previous/np.sqrt(h)
            logh=p[0]+p[2]*np.log(h)+p[1]*(abs(z)-np.sqrt(2/np.pi))+p[3]*z
            h=np.exp(max(-30.,min(30.,logh)))
        else:
            h=p[0]+p[3]*h+(p[2] if previous<0 else p[1])*previous*previous
        out[i]=h
        previous=(r[i]-mu)/scale;active=True
    return out

def reconstruct_volatility(r,seg,fit,seed):
    p=np.array(fit['parameters']); scale=fit['scale']; x=(r-fit['location'])/scale
    h=conditional_variance(r,seg,fit['location'],scale,p,fit['kind']); z=x/np.sqrt(h)
    if fit['kind']==1:
        omega,alpha,beta,gamma=p
        log_next=np.clip(omega+beta*np.log(h)+alpha*(np.abs(z)-np.sqrt(2/np.pi))+gamma*z,-30,30)
        innovations=np.random.default_rng(seed).standard_normal((1024,6))
        innovations=np.vstack([innovations,-innovations])
        offsets=np.zeros(len(innovations)); future=[]
        for j in range(6):
            if j:
                zsim=innovations[:,j-1]
                offsets=omega+beta*offsets+alpha*(np.abs(zsim)-np.sqrt(2/np.pi))+gamma*zsim
            factor=np.exp(np.clip(offsets,-60,60)).mean()
            future.append(np.exp(log_next*beta**j)*factor)
        contribution=gamma*z
    else:
        omega,positive,negative,beta=p
        nxt=omega+beta*h+np.where(x<0,negative,positive)*x*x
        contribution=(negative-positive)*np.where(x<0,x*x,0.)/np.maximum(nxt,1e-12)
        persistence=beta+(positive+negative)/2
        future=[nxt]
        for j in range(1,6): future.append(omega+persistence*future[-1])
    return h*scale**2, np.sum(np.stack(future[1:]),axis=0)*scale**2,z,contribution

def main():
    manifest=json.loads((OUT/'statistics/manifest.json').read_text())
    config=json.loads((OUT/'models/manifest.json').read_text())['config']
    features_core,features_asym=config['direction_features']
    checks=[]; detailed=[]
    for number,record in enumerate(manifest['features'],1):
        file=record['file'];stem=Path(file).stem
        cache=json.loads((OUT/'models/by_file'/f'{stem}.json').read_text())['results']
        fits=cache['fits']
        innerfits={f['model']:f for f in fits if f['stage']=='inner_2016_2018' and f.get('success')}
        if len(innerfits)!=3: continue
        frame=pd.read_parquet(ROOT/record['path'],columns=['date','segment_id','log_return','close'])
        # Reconstruction never loads test observations into the feature design matrix.
        frame=frame.loc[frame.date.lt('2020-01-01')].reset_index(drop=True)
        r=frame.log_return.to_numpy(); seg=frame.segment_id.to_numpy()
        inner=frame.date.lt('2019-01-01').to_numpy(); stage2=~inner
        X=pd.DataFrame(index=frame.index)
        grouped=frame.groupby('segment_id',sort=False).log_return
        for lag in [0,1,2]: X[f'r{lag}']=grouped.shift(lag)
        X['momentum5']=grouped.transform(lambda s:s.rolling(5,min_periods=5).sum())
        X['previous_sign']=np.sign(r)
        for j,(model,short) in enumerate(zip(MODELS,['garch','egarch','gjr'])):
            fit=innerfits[model]
            np.testing.assert_allclose(fit['location'],np.nanmean(r[inner]),rtol=1e-12,atol=1e-15)
            np.testing.assert_allclose(fit['scale'],np.nanstd(r[inner]),rtol=1e-12,atol=1e-15)
            current,variance,z,contribution=reconstruct_volatility(r,seg,fit,42+100*number+j+50)
            sigma=pd.Series(np.sqrt(variance),index=frame.index)
            logvol=np.log(sigma.where(sigma>0))
            X[f'logvol_{short}']=logvol
            X[f'change_{short}']=logvol.groupby(frame.segment_id).diff()
            past_median=sigma.groupby(frame.segment_id).transform(lambda s:s.shift(1).rolling(30,min_periods=15).median())
            X[f'expansion_{short}']=sigma/past_median
            X[f'std_{short}']=r/np.sqrt(current)
            if short=='garch': X['innovation_garch']=z
            else:X[f'{short}_contribution']=contribution
            d2=next(f for f in fits if f['stage']=='direction_2019' and f['model']==f'D2_{"GARCH" if short=="garch" else "EGARCH" if short=="egarch" else "GJR"}_ARMA')
            standard=X[f'std_{short}'].to_numpy()[stage2]
            center=float(np.nanmean(standard)); scale=float(np.nanstd(standard))
            np.testing.assert_allclose([center,scale],[d2['location'],d2['scale']],rtol=1e-11,atol=1e-12)
            checks.append(dict(file=file,model=d2['model'],n=int(np.isfinite(standard).sum()),
                normalization_period='2019 only',center_max_abs_error=abs(center-d2['location']),scale_max_abs_error=abs(scale-d2['scale'])))
        X['difference_egarch']=X.logvol_egarch-X.logvol_garch
        X['difference_gjr']=X.logvol_gjr-X.logvol_garch
        X=X.replace([np.inf,-np.inf],np.nan)
        # Independently establish fully observed, settled t+1..t+6 labels.
        target=np.full(len(frame),np.nan); ix=np.arange(max(0,len(frame)-6)); valid=seg[ix]==seg[ix+6]
        for step in range(1,7):valid &= np.isfinite(r[ix+step])
        close=frame.close.to_numpy(); valid &= (close[ix+1]>0)&(close[ix+6]>0)&np.isfinite(close[ix+1])&np.isfinite(close[ix+6])
        target[ix[valid]]=np.log(close[ix[valid]+6]/close[ix[valid]+1])
        grid=((frame.date.dt.hour*60+frame.date.dt.minute)%6==0).to_numpy()
        settled=(frame.date+pd.Timedelta(minutes=6)).lt('2020-01-01').to_numpy()
        for model,columns in [('D3_Logistic_Core',features_core),('D3_Logistic_Asymmetric',features_asym)]:
            fit=next(f for f in fits if f['model']==model and f['stage']=='direction_2019')
            matrix=X[columns].to_numpy()
            available=stage2&grid&settled&np.isfinite(target)&np.isfinite(matrix).all(axis=1)
            design=matrix[available]
            center=design.mean(axis=0); scale=design.std(axis=0); scale=np.where(scale>1e-12,scale,1.)
            assert len(design)==fit['n'],(file,model,len(design),fit['n'])
            np.testing.assert_allclose(center,fit['center'],rtol=1e-11,atol=1e-12)
            np.testing.assert_allclose(scale,fit['scale'],rtol=1e-11,atol=1e-12)
            for j,column in enumerate(columns):
                detailed.append(dict(file=file,model=model,feature=column,n=len(design),
                    reconstructed_center=center[j],cached_center=fit['center'][j],
                    reconstructed_scale=scale[j],cached_scale=fit['scale'][j]))
            checks.append(dict(file=file,model=model,n=len(design),normalization_period='2019 settled labels / predictors from2016-2018 volatility fits',
                center_max_abs_error=float(np.max(np.abs(center-fit['center']))),scale_max_abs_error=float(np.max(np.abs(scale-fit['scale'])))))
        if number%9==0:print(f'{number}/54 training-normalization audits',flush=True)
    result=pd.DataFrame(checks);result.to_csv(CODE/'training_normalization_checks.csv',index=False)
    pd.DataFrame(detailed).to_csv(CODE/'training_normalization_features.csv',index=False)
    summary=dict(status='passed',files=result.file.nunique(),models=result.model.nunique(),fit_checks=len(result),
        logistic_feature_checks=len(detailed),center_max_abs_error=float(result.center_max_abs_error.max()),
        scale_max_abs_error=float(result.scale_max_abs_error.max()),
        no_test_rows_loaded_into_feature_reconstruction=True,optimizer_called=False,
        standardization='r[t] divided by forecast sigma[t|t-1], not sigma[t+1|t]; conditional state uses only previous observed returns. Raw numerator convention retained from07.')
    (CODE/'training_normalization_findings.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
