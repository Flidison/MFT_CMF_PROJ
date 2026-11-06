"""Lecturer-feedback diagnostics. Existing audited artifacts are read-only.

Run from anywhere with the project's venv/bin/python. No model is fitted here.
Minute lags never cross a saved segment, clock gap, or delivery-contract change.
"""
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import json, hashlib, warnings, platform, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist, squareform, cdist
from scipy.optimize import linear_sum_assignment, curve_fit
from statsmodels.tsa.stattools import adfuller, kpss
from numba import njit

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parents[1]
SRC = ROOT / 'artifacts/research_54'
VERSION = 'feedback-v1.2'
MAXLAG = 120
for name in ['tables', 'chart_data', 'figures', '_build', '_build/product_cache']:
    (OUT/name).mkdir(parents=True, exist_ok=True)

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def save(name, rows):
    d = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    keys=[k for k in ['product','file','period','stage','model','series','sample','lag','third','month','rank','event_rank','offset_rows','slice','shape','k','comparison'] if k in d.columns]
    if keys:d=d.sort_values(keys,kind='stable').reset_index(drop=True)
    d.to_csv(OUT/'tables'/f'{name}.csv', index=False, float_format='%.17g')
    return d

@njit(cache=True)
def acf_kernel(z, seg, vol, maxlag, volume_sensitivity=True):
    """Pair-specific Pearson correlations, with stable globally centered inputs.

    Count and five sufficient statistics per series/sample/lag. Endpoint eligibility
    selects pairs without deleting rows. Segment equality implies all intermediate
    timestamps exist, verified independently before this function is called.
    """
    ns = 2 if volume_sensitivity else 1
    sums = np.zeros((ns, z.shape[1], maxlag, 6))
    for lag in range(1, maxlag+1):
        for i in range(lag, len(z)):
            if seg[i] != seg[i-lag]:
                continue
            vgood = vol[i] > 0 and vol[i-lag] > 0
            for j in range(z.shape[1]):
                a, b = z[i,j], z[i-lag,j]
                if not np.isfinite(a) or not np.isfinite(b):
                    continue
                for s in range(ns):
                    if s == 1 and not vgood:
                        continue
                    sums[s,j,lag-1,0] += 1
                    sums[s,j,lag-1,1] += a
                    sums[s,j,lag-1,2] += b
                    sums[s,j,lag-1,3] += a*a
                    sums[s,j,lag-1,4] += b*b
                    sums[s,j,lag-1,5] += a*b
    return sums

def acf_table(values, seg, vol, names, maxlag, sensitivity=True):
    z = np.column_stack(values).astype(float)
    for j in range(z.shape[1]):
        ok = np.isfinite(z[:,j])
        sd = np.std(z[ok,j]) if ok.any() else 0
        if sd > 0:
            z[:,j] = (z[:,j]-np.mean(z[ok,j]))/sd
    s = acf_kernel(z, seg.astype(np.int64), vol, maxlag, sensitivity)
    rows = []
    for sample, name in enumerate(['all', 'positive_volume_pairs'][:s.shape[0]]):
        for j, series in enumerate(names):
            for lag in range(1,maxlag+1):
                n,a,b,aa,bb,ab = s[sample,j,lag-1]
                den = np.sqrt(max(0,aa-a*a/max(n,1))*max(0,bb-b*b/max(n,1)))
                rho = (ab-a*b/n)/den if n>=3 and den>1e-20 else np.nan
                rows.append(dict(series=series,lag=lag,sample=name,pairs=int(n),acf=rho))
    return pd.DataFrame(rows)

@njit(cache=True)
def filter_variance(r, seg, mu, scale, p, kind):
    h = np.full(len(r), np.nan)
    active = False
    prev, hp, hits = 0., 1., 0
    for i in range(len(r)):
        if not np.isfinite(r[i]):
            active = False
            continue
        fresh = not active or i==0 or seg[i]!=seg[i-1]
        if fresh:
            cur=1.
        elif kind==1:
            z=prev/np.sqrt(hp)
            logh=p[0]+p[2]*np.log(hp)+p[1]*(abs(z)-np.sqrt(2/np.pi))+p[3]*z
            if logh < -30 or logh > 30:
                hits += 1
            cur=np.exp(min(30.,max(-30.,logh)))
        else:
            cur=p[0]+p[3]*hp+(p[2] if prev<0 else p[1])*prev*prev
        h[i]=cur
        prev=(r[i]-mu)/scale
        hp=cur
        active=True
    return h, hits

def finite_runs(x, seg):
    ok=np.isfinite(x)
    starts=np.flatnonzero(ok & np.r_[True,(~ok[:-1]) | (seg[1:]!=seg[:-1])])
    ends=np.flatnonzero(ok & np.r_[(~ok[1:]) | (seg[1:]!=seg[:-1]),True])+1
    assert len(starts)==len(ends)
    return list(zip(starts,ends))

def tests_on_runs(x, seg, dates, metadata):
    """Three chronological thirds, longest finite run per third (>=60 points).

    Standard ADF/KPSS are never run on concatenated sessions. Fixed 5 lags.
    These are short-window diagnostics, not tests of global strict stationarity.
    """
    runs=finite_runs(x,seg)
    result=[]
    cuts=np.linspace(0,len(x),4,dtype=int)
    for third in range(3):
        candidates=[(a,b) for a,b in runs if cuts[third]<=a<cuts[third+1] and b-a>=60]
        if not candidates:
            result.append(dict(**metadata,third=third+1,status='no_contiguous_run_60',n=0))
            continue
        a,b=max(candidates,key=lambda p:(p[1]-p[0],-p[0]))
        y=x[a:b]
        common=dict(**metadata,third=third+1,start=str(dates[a]),end=str(dates[b-1]),segment=int(seg[a]),n=len(y),adf_lags=5,kpss_lags=5)
        if np.ptp(y)==0:
            result.append(dict(**common,status='constant'))
            continue
        y=(y-np.mean(y))/np.std(y)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            ad=adfuller(y,maxlag=5,regression='c',autolag=None)
            kp=kpss(y,regression='c',nlags=5)
        result.append(dict(**common,status='ok',adf_stat=ad[0],adf_p=ad[1],kpss_stat=kp[0],kpss_p=kp[1],
                           adf_reject5=ad[1]<.05,kpss_reject5=kp[1]<.05,
                           warning='; '.join(str(w.message) for w in caught)))
    return result

def direct_corr(a,b):
    return float(np.corrcoef(a,b)[0,1]) if len(a)>2 and np.ptp(a)>0 and np.ptp(b)>0 else np.nan

def process_product(record):
    path=ROOT/record['path']
    file=record['file']; product=file.split('9999')[0]
    cache=OUT/'_build/product_cache'/f'{product}.json'
    source_hash=sha(path)
    assert source_hash==record['sha256'], 'Feature file differs from audited manifest: '+file
    cache_key=source_hash+'_'+VERSION
    if cache.exists():
        old=json.loads(cache.read_text())
        if old['cache_key']==cache_key:
            return old['results']
    b=pd.read_parquet(path)
    r=b.log_return.to_numpy(); seg=b.segment_id.to_numpy(); v=b.volume.to_numpy()
    t=b.date.to_numpy(); ns=t.astype('datetime64[ns]').astype(np.int64)
    close=b.close.to_numpy(); symbols=b.symbol.to_numpy()
    # Independent alignment/return checks on all source rows, all 54 products.
    same=seg[1:]==seg[:-1]
    assert np.all(ns[1:][same]-ns[:-1][same]==60_000_000_000),file
    assert np.all(symbols[1:][same]==symbols[:-1][same]),file
    priceok=same & np.isfinite(close[1:]) & np.isfinite(close[:-1]) & (close[1:]>0)&(close[:-1]>0)
    expected=np.full(len(r),np.nan); expected[np.flatnonzero(priceok)+1]=np.log(close[1:][priceok]/close[:-1][priceok])
    np.testing.assert_allclose(r,expected,rtol=1e-8,atol=3e-15,equal_nan=True)
    result={k:[] for k in ['acf','micro','segments','checks','stationarity','residual_acf','residual_summary','moments','extremes','event_windows','tail_sensitivity','tail_survival','decay','residual_moments']}
    result['checks'].append(dict(file=file,check='all_rows_clock_symbol_returns',n=len(b),max_abs_error=float(np.nanmax(np.abs(r-expected))),passed=True))
    fullfits=pd.read_csv(SRC/'models/fits.csv')
    fits=fullfits[(fullfits.file==file)&(fullfits.stage=='full_train')&fullfits.model.isin(['V1_GARCH','V2_EGARCH','V3_GJR_GARCH'])].to_dict('records')
    if not fits and product=='SA':
        fits=[f for f in json.loads((SRC/'backtest/sa_short_history_fits.json').read_text()) if f['model'] in ['V1_GARCH','V2_EGARCH','V3_GJR_GARCH']]
        for f in fits:
            f['fit_scope']='08_extension_19_train_dates'
    filtered={}
    for f in fits:
        p=np.asarray(json.loads(f['parameters']) if isinstance(f['parameters'],str) else f['parameters'],float)
        h,hits=filter_variance(r,seg,float(f['location']),float(f['scale']),p,int(f['kind']))
        z=(r-float(f['location']))/(float(f['scale'])*np.sqrt(h))
        filtered[f['model']]=(z,h,f.get('fit_scope','07_full_train'),hits)
    train=t<np.datetime64('2020-01-01')
    for period,mask in [('train',train),('test',~train),('early_train',t<np.datetime64('2018-01-01')),('late_train',(t>=np.datetime64('2018-01-01'))&train)]:
        rr=r[mask];ss=seg[mask];vv=v[mask];tt=t[mask]
        if not len(rr):
            continue
        sensitivity=period in ['train','test']
        names=['r','abs_r','sq_r']+(['abs_deseasonalized_r'] if sensitivity else [])
        values=[rr,np.abs(rr),rr**2]+([np.abs(b.deseasonalized_log_return.to_numpy()[mask])] if sensitivity else [])
        ac=acf_table(values,ss,vv,names,MAXLAG if sensitivity else 60,sensitivity)
        ac['file']=file;ac['product']=product;ac['period']=period
        result['acf']+=ac.to_dict('records')
        if not sensitivity:
            continue
        # Independent timestamp-index join for four products, including unusual tails.
        if product in ['NI','FU','TF','RB','AU','C']:
            frame=pd.DataFrame({'date':tt,'segment':ss,'symbol':b.symbol.to_numpy()[mask],'r':rr,'v':vv})
            for lag in [1,2,5,30,60,120]:
                later=frame.copy();earlier=frame.copy();earlier['date']+=pd.Timedelta(minutes=lag)
                m=later.merge(earlier,on=['date','segment','symbol'],suffixes=('_now','_past'))
                for scope in ['all','positive_volume_pairs']:
                    good=np.isfinite(m.r_now)&np.isfinite(m.r_past)
                    if scope!='all': good&=(m.v_now>0)&(m.v_past>0)
                    for name,fn in [('r',lambda x:x),('abs_r',np.abs),('sq_r',lambda x:x*x)]:
                        actual=direct_corr(fn(m.loc[good,'r_now'].to_numpy()),fn(m.loc[good,'r_past'].to_numpy()))
                        old=ac[(ac['sample']==scope)&(ac.series==name)&(ac.lag==lag)].iloc[0]
                        assert int(old.pairs)==good.sum(),(file,period,lag)
                        error=abs(actual-old.acf)
                        assert error<1e-10 or (np.isnan(actual)&np.isnan(old.acf)),(file,period,lag,error)
                        result['checks'].append(dict(file=file,period=period,check='timestamp_join_'+scope,series=name,lag=lag,n=int(good.sum()),max_abs_error=error,passed=True))
        runs=finite_runs(rr,ss); lens=np.array([bb-aa for aa,bb in runs])
        result['segments'].append(dict(file=file,product=product,period=period,returns=int(np.isfinite(rr).sum()),runs=len(lens),median_run=int(np.median(lens)),max_run=int(max(lens)),p90_run=float(np.quantile(lens,.9)),runs_ge_60=int((lens>=60).sum()),runs_ge_120=int((lens>=120).sum()),runs_ge_256=int((lens>=256).sum())))
        valid=(ss[1:]==ss[:-1])&np.isfinite(rr[1:])&np.isfinite(rr[:-1])
        for scope,eligible in [('all',np.ones(len(rr),bool)),('positive_volume_pairs',vv>0),('nonzero_return_pairs',rr!=0),('positive_price_legs', (vv>0)&np.r_[False,vv[:-1]>0])]:
            good=valid&eligible[1:]&eligible[:-1]
            x,y=rr[1:][good],rr[:-1][good]
            cov=float(np.cov(x,y,ddof=0)[0,1]) if len(x)>2 else np.nan
            result['micro'].append(dict(file=file,product=product,period=period,sample=scope,pairs=len(x),acf1=direct_corr(x,y),sign_reversal_share=float(np.mean(x*y<0)),lag1_covariance=cov,roll_covariance_spread_proxy_bp=20000*np.sqrt(max(0,-cov)),zero_return_share=float(np.mean(rr[np.isfinite(rr)]==0)),zero_volume_share=float(np.mean(vv==0))))
        nz=np.isfinite(rr)
        stale=finite_runs(np.where(rr==0,0,np.nan),ss)
        result['micro'][-1]['max_stale_zero_return_minutes']=max([bb-aa for aa,bb in stale],default=0)
        for name,x in [('r',rr),('abs_r',np.abs(rr)),('sq_r',rr**2)]:
            result['stationarity']+=tests_on_runs(x,ss,tt,dict(file=file,product=product,period=period,series=name,model='observed',scope='representative_contiguous_runs'))
        part=b.loc[mask].copy();part['month']=part.date.dt.strftime('%Y-%m');part['r2']=part.log_return**2
        for month,g in part.groupby('month',sort=False):
            q=g.log_return.dropna().to_numpy()
            if len(q):result['moments'].append(dict(file=file,product=product,period=period,month=month,n=len(q),mean=float(q.mean()),std=float(q.std(ddof=1)),excess_kurtosis=float(stats.kurtosis(q,bias=False)),zero_return_share=float(np.mean(q==0))))
        for model,(zz,hh,scope,hits) in filtered.items():
            z=zz[mask];h=hh[mask]
            residual=acf_table([z,np.abs(z),z*z,h],ss,vv,['z','abs_z','sq_z','filtered_h'],60,False)
            residual['file']=file;residual['product']=product;residual['period']=period;residual['model']=model;residual['fit_scope']=scope
            result['residual_acf']+=residual.to_dict('records')
            fin=z[np.isfinite(z)]
            result['residual_summary'].append(dict(file=file,product=product,period=period,model=model,fit_scope=scope,n=len(fin),mean=float(fin.mean()),variance=float(fin.var()),excess_kurtosis=float(stats.kurtosis(fin,bias=False)),filter_clip_hits_all_periods=hits,innovation_negative_second_moment_weight=float(np.sum(fin[fin<0]**2)/np.sum(fin**2))))
            for name,x in [('z',z),('abs_z',np.abs(z)),('sq_z',z*z),('filtered_h',h)]:
                result['stationarity']+=tests_on_runs(x,ss,tt,dict(file=file,product=product,period=period,series=name,model=model,fit_scope=scope,scope='representative_contiguous_runs'))
            q=pd.DataFrame({'month':part.month.to_numpy(),'z':z,'h':h})
            for month,g in q.groupby('month',sort=False):
                result['residual_moments'].append(dict(file=file,product=product,period=period,month=month,model=model,n=int(g.z.count()),z_mean=float(g.z.mean()),z_variance=float(g.z.var()),mean_h=float(g.h.mean())))
        if product in ['NI','FU','TF']:
            idx=np.flatnonzero(mask & np.isfinite(r));top=idx[np.argsort(np.abs(r[idx]))[-20:][::-1]]
            for rank,i in enumerate(top,1):
                d=dict(file=file,product=product,period=period,rank=rank,ID=int(b.ID.iloc[i]),date=str(t[i]),symbol=symbols[i],segment=int(seg[i]),return_bp=float(r[i]*10000),previous_close=float(close[i-1]),close=float(close[i]),volume=float(v[i]),previous_volume=float(v[i-1]),high=float(b.high.iloc[i]),low=float(b.low.iloc[i]),ohlc_consistent=bool(b.low.iloc[i]<=close[i]<=b.high.iloc[i]),next_return_bp=float(r[i+1]*10000) if i+1<len(r) and seg[i+1]==seg[i] else np.nan)
                result['extremes'].append(d)
                if rank<=3:
                    for j in range(max(0,i-5),min(len(r),i+6)):
                        result['event_windows'].append(dict(file=file,product=product,period=period,event_rank=rank,event_ID=int(b.ID.iloc[i]),offset_rows=j-i,ID=int(b.ID.iloc[j]),date=str(t[j]),symbol=symbols[j],segment=int(seg[j]),close=float(close[j]),volume=float(v[j]),return_bp=float(r[j]*10000)))
            fin=rr[np.isfinite(rr)]; order=np.argsort(np.abs(fin))[::-1]
            slices={'all':fin,'positive_volume_bar':rr[np.isfinite(rr)&(vv>0)],'positive_price_legs':rr[np.isfinite(rr)&(vv>0)&np.r_[False,vv[:-1]>0]],'nonzero_returns':fin[fin!=0],
                    'hypothetical_exclude_largest_1':np.delete(fin,order[:1]),'hypothetical_exclude_largest_5':np.delete(fin,order[:5]),'hypothetical_exclude_largest_0.1pct':np.delete(fin,order[:max(1,int(np.ceil(.001*len(fin))))])}
            for label,q in slices.items():
                result['tail_sensitivity'].append(dict(file=file,product=product,period=period,slice=label,n=len(q),excess_kurtosis=float(stats.kurtosis(q,bias=False)),std_bp=float(q.std(ddof=1)*10000),min_bp=float(q.min()*10000),max_bp=float(q.max()*10000),diagnostic_only=label.startswith('hypothetical')))
            for k in np.r_[np.arange(.5,10,.5),[10,15,20,30,40,50]]:
                prob=float(np.mean(np.abs(fin-fin.mean())>k*fin.std(ddof=1)))
                result['tail_survival'].append(dict(file=file,product=product,period=period,threshold_sigma=float(k),count=int(round(prob*len(fin))),n=len(fin),probability=prob))
    for key in result:
        for row in result[key]:
            for k,x in list(row.items()):
                if isinstance(x,np.generic):row[k]=x.item()
    cache.write_text(json.dumps(dict(cache_key=cache_key,results=result),allow_nan=True))
    return result

def adjusted_rand(a,b):
    tab=pd.crosstab(np.asarray(a),np.asarray(b)).to_numpy()
    comb=lambda x: np.sum(x*(x-1)/2)
    n=tab.sum(); total=n*(n-1)/2
    index=comb(tab);expected=comb(tab.sum(0))*comb(tab.sum(1))/total
    maxindex=.5*(comb(tab.sum(0))+comb(tab.sum(1)))
    return float((index-expected)/(maxindex-expected)) if maxindex!=expected else 1.

def silhouette(X, labels):
    dist=squareform(pdist(X));scores=[]
    for i in range(len(X)):
        same=labels==labels[i]
        if same.sum()==1:scores.append(0.);continue
        a=dist[i,same].sum()/(same.sum()-1)
        bb=min(dist[i,labels==j].mean() for j in np.unique(labels) if j!=labels[i])
        scores.append((bb-a)/max(a,bb))
    return float(np.mean(scores))

def cluster_features(acf):
    rows=[]
    for (period,product),g in acf[acf['sample']=='all'].groupby(['period','product']):
        def take(series,lo,hi):
            return g[(g.series==series)&g.lag.between(lo,hi)].acf.mean()
        pairs=g[(g.series=='r')&(g.lag==1)].pairs.iloc[0]
        rows.append(dict(period=period,product=product,r1=take('r',1,1),r2_5=take('r',2,5),a1=take('abs_r',1,1),a5_15=take('abs_r',5,15),a30_60=take('abs_r',30,60),s30_60=take('sq_r',30,60),lag1_pairs=pairs))
    f=pd.DataFrame(rows);cols=['r1','r2_5','a1','a5_15','a30_60','s30_60']
    tr=f[f.period=='train'].set_index('product').sort_index();te=f[f.period=='test'].set_index('product').reindex(tr.index)
    center=tr[cols].median();scale=tr[cols].quantile(.75)-tr[cols].quantile(.25);scale=scale.replace(0,1)
    X=((tr[cols]-center)/scale).to_numpy();Xt=((te[cols]-center)/scale).to_numpy()
    Z=linkage(X,method='ward');candidates=[]
    for k in range(2,7):
        labels=fcluster(Z,k,criterion='maxclust')
        candidates.append(dict(k=k,silhouette=silhouette(X,labels),minimum_cluster_size=int(np.bincount(labels)[1:].min())))
    candidates=pd.DataFrame(candidates);k=int(candidates.loc[candidates.silhouette.idxmax(),'k'])
    lab=fcluster(Z,k,criterion='maxclust')
    # Names ordered by train median return lag-1, without using test data.
    order=sorted(np.unique(lab),key=lambda j:tr.r1.to_numpy()[lab==j].mean())
    mapping={old:new+1 for new,old in enumerate(order)};lab=np.array([mapping[i] for i in lab])
    centers=np.array([X[lab==i].mean(0) for i in range(1,k+1)])
    test_nearest=np.argmin(cdist(Xt,centers),axis=1)+1
    test_ind=fcluster(linkage(Xt,method='ward'),k,criterion='maxclust')
    result=tr.reset_index().copy();result['train_cluster']=lab;result['test_nearest_train_centroid']=test_nearest;result['test_independent_cluster']=test_ind
    result['test_centroid_agrees']=lab==test_nearest
    stability=[dict(comparison='train_vs_test_independent',n=len(tr),ari=adjusted_rand(lab,test_ind),assignment_agreement=float(np.mean(lab==test_nearest)))]
    for period in ['early_train','late_train']:
        p=f[f.period==period].set_index('product').reindex(tr.index)
        eligible=p[cols].notna().all(axis=1)&(p.lag1_pairs>=5000)
        xx=((p.loc[eligible,cols]-center)/scale).to_numpy()
        ll=fcluster(linkage(xx,method='ward'),k,criterion='maxclust')
        stability.append(dict(comparison='full_train_vs_'+period,n=int(eligible.sum()),ari=adjusted_rand(lab[eligible],ll),assignment_agreement=None))
    stable=(candidates.silhouette.max()>=.25 and min(s['ari'] for s in stability)>=.5 and np.mean(lab==test_nearest)>=.75 and candidates.loc[candidates.k==k,'minimum_cluster_size'].iloc[0]>=5)
    save('clustering_features',f);save('clustering_scaler',pd.DataFrame({'feature':cols,'train_median':center,'train_iqr':scale}));save('clustering_candidates',candidates);save('clustering_assignments',result);save('clustering_stability',stability)
    np.save(OUT/'chart_data/ward_linkage.npy',Z)
    info=dict(k=k,training_silhouette=float(candidates.silhouette.max()),stable_groups=bool(stable),criteria='silhouette>=.25, all ARI>=.50, centroid agreement>=.75, smallest group>=5; descriptive predeclared guardrails, not a formal test',stability=stability)
    (OUT/'tables/clustering_summary.json').write_text(json.dumps(info,indent=2))
    return info

def persistence():
    f=pd.read_csv(SRC/'models/fits.csv');f=f[f.model.isin(['V1_GARCH','V3_GJR_GARCH','V2_EGARCH'])].copy()
    extension=[{**r,'stage':'08_extension_19_dates'} for r in json.loads((SRC/'backtest/sa_short_history_fits.json').read_text()) if r['model'] in ['V1_GARCH','V2_EGARCH','V3_GJR_GARCH']]
    for r in extension:r['parameters']=json.dumps(r['parameters'])
    f=pd.concat([f,pd.DataFrame(extension)],ignore_index=True)
    rows=[]
    for row in f.to_dict('records'):
        p=json.loads(row['parameters']);kind=int(row['kind'])
        row['product']=row['file'].split('9999')[0]
        if kind==1:
            row.update(omega_scaled=p[0],alpha_positive=np.nan,alpha_negative=np.nan,beta_actual=p[2],persistence_recomputed=p[2],formula='EGARCH log variance beta only; not finite-variance criterion')
        else:
            row.update(omega_scaled=p[0],omega_return_variance=p[0]*float(row['scale'])**2,alpha_positive=p[1],alpha_negative=p[2],beta_actual=p[3],persistence_recomputed=p[3]+.5*(p[1]+p[2]),formula='beta+(positive+negative)/2 under symmetric unit-variance innovations')
            if kind==0:np.testing.assert_allclose(p[1],p[2],atol=1e-14)
        np.testing.assert_allclose(row['persistence_recomputed'],row['persistence'],atol=2e-14)
        row['near_unit_0_98']=row['persistence_recomputed']>=.98
        row['near_unit_0_99']=row['persistence_recomputed']>=.99
        row['near_constraint_0_998']=row['persistence_recomputed']>=.998
        row['finite_variance_symmetric_condition']=row['persistence_recomputed']<1 if kind!=1 else np.nan
        row['half_life_minutes_formal']=np.log(.5)/np.log(row['persistence_recomputed'])
        rows.append(row)
    d=save('model_parameters_persistence',rows)
    summ=[]
    for (stage,model),g in d.groupby(['stage','model']):
        summ.append(dict(stage=stage,model=model,n=len(g),median=g.persistence_recomputed.median(),minimum=g.persistence_recomputed.min(),maximum=g.persistence_recomputed.max(),ge_0_98=int(g.near_unit_0_98.sum()),ge_0_99=int(g.near_unit_0_99.sum()),ge_0_998=int(g.near_constraint_0_998.sum()),ge_1=int((g.persistence_recomputed>=1).sum()),boundary=int(g.boundary.sum())))
    save('persistence_summary',summ)
    a=d.pivot(index=['file','product','model'],columns='stage',values='persistence_recomputed').reset_index()
    a['full_minus_inner']=a.full_train-a.inner_2016_2018
    save('persistence_training_window_changes',a)
    save('persistence_top_cases',d[d.stage=='full_train'].sort_values('persistence_recomputed',ascending=False).groupby('model').head(10))
    return summ

def decay_diagnostics(ac):
    rows=[]
    for (product,period,series),g in ac[(ac['sample']=='all')&ac.series.isin(['abs_r','sq_r','abs_deseasonalized_r'])&ac.period.isin(['train','test'])].groupby(['product','period','series']):
        g=g[g.lag.between(5,60)&g.acf.notna()&(g.pairs>=100)].sort_values('lag')
        if len(g)<30:continue
        x=g.lag.to_numpy(float);y=g.acf.to_numpy(float)
        exp=lambda x,a,b:a*np.exp(-b*(x-5))
        hyp=lambda x,a,b:a*(x/5)**(-b)
        for name,fun in [('exponential',exp),('hyperbolic',hyp)]:
            try:
                par,_=curve_fit(fun,x,y,p0=[max(.001,min(.99,y[0])),.05 if name=='exponential' else .2],bounds=([0,0],[1,10]),maxfev=10000)
                pred=fun(x,*par);rss=float(np.sum((y-pred)**2))
                rows.append(dict(product=product,period=period,series=series,shape=name,n_lags=len(g),amplitude=par[0],decay_rate=par[1],rss=rss,aic_descriptive=len(g)*np.log(max(rss/len(g),1e-30))+4,warning='Correlated ACF ordinates, finite 5-60min horizon; shape comparison is descriptive, not long-memory proof'))
            except (RuntimeError,ValueError):pass
    save('decay_shape_comparison',rows)

def reconcile(ac):
    old=pd.read_csv(SRC/'statistics/acf.csv');name={'log_return':'r','abs_log_return':'abs_r','squared_log_return':'sq_r','abs_deseasonalized_log_return':'abs_deseasonalized_r'}
    old=old[old.series.isin(name)&old.period.isin(['train','test'])].copy();old['series']=old.series.map(name)
    joined=old.merge(ac,on=['file','period','series','lag','sample'],suffixes=('_old','_new'),validate='one_to_one')
    joined['error']=abs(joined.acf_old-joined.acf_new);joined['pairs_match']=joined.pairs_old==joined.pairs_new
    assert joined.pairs_match.all() and joined.error.max()<1e-10
    save('acf_reconciliation',joined[['file','period','series','lag','sample','acf_old','acf_new','pairs_old','pairs_new','error','pairs_match']])
    return dict(rows=len(joined),max_abs_error=float(joined.error.max()),pair_counts_identical=bool(joined.pairs_match.all()))

def main():
    started=time.monotonic()
    manifest=json.loads((SRC/'statistics/manifest.json').read_text());records=manifest['features']
    assert len(records)==54
    allresults={}
    with ProcessPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(process_product,r):r['file'] for r in records}
        for n,future in enumerate(as_completed(futures),1):
            res=future.result()
            for key,rows in res.items():allresults.setdefault(key,[]).extend(rows)
            print(f'{n}/54 {futures[future]} complete ({time.monotonic()-started:.0f}s)',flush=True)
    frames={k:save(k,rows) for k,rows in allresults.items() if rows}
    ac=frames['acf'];rec=reconcile(ac)
    clusters=cluster_features(ac);pers=persistence();decay_diagnostics(ac)
    source_paths=[ROOT/p for p in ['04_liquidity_activity.ipynb','05_research_statistics_features_54.ipynb','06_strategies_hypotheses_54.ipynb','07_forecasting_models_54.ipynb','08_backtest_fees_risk_54.ipynb','09_final_audit_07_08.ipynb']]
    source_paths += [SRC/p for p in ['final_audit_07_08.md','final_strategy_comparison.csv','execution_diagnostics.csv','fee_audit.csv','volatility_model_comparison.csv','presentation_findings.md','models/fits.csv','models/manifest.json','statistics/manifest.json','statistics/acf.csv','statistics/tails.csv']]
    source_paths += [ROOT/r['path'] for r in records]
    provenance=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size) for p in source_paths]
    (OUT/'tables/source_manifest.json').write_text(json.dumps(dict(version=VERSION,inputs=provenance,python=sys.version,platform=platform.platform(),elapsed_seconds=time.monotonic()-started),indent=2))
    summary=dict(acf_reconciliation=rec,clustering=clusters,persistence=pers,maximum_contiguous_returns=int(frames['segments'].max_run.max()),outputs={k:len(v) for k,v in frames.items()})
    (OUT/'tables/analysis_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
