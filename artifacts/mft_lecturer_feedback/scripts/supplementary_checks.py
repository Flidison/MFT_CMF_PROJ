"""Raw-CSV event checks, segment-centering sensitivity, forecast-filter validation."""
from analyze_feedback import *

def main():
    acrows=[]; rawrows=[];tailrows=[];filterchecks=[];events=[]
    manifest=json.loads((SRC/'statistics/manifest.json').read_text())
    fits=pd.read_csv(SRC/'models/fits.csv')
    for n,record in enumerate(manifest['features'],1):
        file=record['file'];code=file.split('9999')[0]
        b=pd.read_parquet(ROOT/record['path']);r=b.log_return.to_numpy();s=b.segment_id.to_numpy();v=b.volume.to_numpy()
        for period,part in b.groupby('period',sort=False):
            rr=part.log_return.to_numpy();ss=part.segment_id.to_numpy()
            centered={}
            for series,x in [('r',rr),('abs_r',np.abs(rr)),('sq_r',rr*rr)]:
                groups=pd.Series(x).groupby(ss).transform('mean').to_numpy()
                z=x-groups
                for lag in [1,5,10,30,60]:
                    good=(ss[lag:]==ss[:-lag])&np.isfinite(z[lag:])&np.isfinite(z[:-lag])
                    acrows.append(dict(file=file,product=code,period=period,series=series,lag=lag,pairs=int(good.sum()),acf=direct_corr(z[lag:][good],z[:-lag][good]),sample='within_segment_demeaned',interpretation='Ex-post diagnostic removes between-session level variation; finite-run demeaning induces negative bias at long lags'))
        if code in ['NI','FU','TF','RB','AU','C']:
            forecast=pd.read_parquet(SRC/'models/forecasts'/f'{Path(file).stem}.parquet')
            pos=b.set_index('ID').index.get_indexer(forecast.ID)
            for f in fits[(fits.file==file)&(fits.stage=='full_train')&fits.model.isin(['V1_GARCH','V2_EGARCH','V3_GJR_GARCH'])].to_dict('records'):
                p=np.array(json.loads(f['parameters']));h,hits=filter_variance(r,s,float(f['location']),float(f['scale']),p,int(f['kind']))
                x=(r-float(f['location']))/float(f['scale'])
                if int(f['kind'])==1:
                    z=x/np.sqrt(h);pred=np.exp(np.clip(p[0]+p[2]*np.log(h)+p[1]*(np.abs(z)-np.sqrt(2/np.pi))+p[3]*z,-30,30))*float(f['scale'])**2
                else:pred=(p[0]+p[3]*h+np.where(x<0,p[2],p[1])*x*x)*float(f['scale'])**2
                actual=forecast[f'variance_{f["model"]}_h1'].to_numpy()
                np.testing.assert_allclose(pred[pos],actual,rtol=1e-11,atol=1e-18,equal_nan=True)
                filterchecks.append(dict(file=file,product=code,model=f['model'],n=len(pos),max_abs_error=float(np.nanmax(np.abs(pred[pos]-actual))),passed=True))
        if code not in ['NI','FU','TF']:continue
        rawpath=ROOT/'fut_data'/file
        raw=pd.read_csv(rawpath,parse_dates=['date'])
        ex=pd.read_csv(OUT/'tables/extremes.csv');ex=ex[ex.file==file]
        for e in ex.to_dict('records'):
            i=int(b.index[b.ID==e['ID']][0]);row=b.iloc[i]
            matches=raw[(raw.date==row.date)&(raw.symbol==row.symbol)]
            if len(matches)!=1:raise ValueError((file,row.date,len(matches)))
            orig=matches.iloc[0]
            fields=['open','high','low','close','volume','money','open_interest']
            error=max(abs(float(orig[k])-float(row[k])) for k in fields)
            assert error<1e-10
            past=b.iloc[max(0,i-30):i];future=b.iloc[i+1:min(len(b),i+31)]
            future=future[future.symbol==row.symbol]
            price_pre=float(past[past.symbol==row.symbol].close.median());price_post=float(future.close.median()) if len(future) else np.nan
            prior_zeros=0
            for j in range(i-1,max(-1,i-31),-1):
                if s[j]!=s[i] or not np.isfinite(r[j]) or r[j]!=0:break
                prior_zeros+=1
            d=dict(**e,raw_csv_sha256=sha(rawpath),raw_fields_match=True,max_field_error=error,raw_date_duplicates=int((raw.date==row.date).sum()),previous_30_bar_median=price_pre,next_30_bar_same_symbol_median=price_post,post_pre_median_ratio=price_post/price_pre,close_pre_median_ratio=float(row.close/price_pre),preceding_zero_return_run=prior_zeros,segment_last_return=bool(i==len(b)-1 or s[i+1]!=s[i]),next_bar_gap_minutes=float((b.date.iloc[i+1]-row.date).total_seconds()/60) if i+1<len(b) else np.nan)
            rawrows.append(d)
        # Actual price-level context stays on the clock, including explicit gaps.
        for period in ['train','test']:
            ee=ex[(ex.period==period)&(ex['rank']==1)].iloc[0];i=int(b.index[b.ID==ee.ID][0])
            for j in range(max(0,i-30),min(len(b),i+31)):
                q=b.iloc[j]
                events.append(dict(product=code,period=period,event_date=ee.date,offset_rows=j-i,clock_minutes=float((q.date-b.date.iloc[i]).total_seconds()/60),date=str(q.date),symbol=q.symbol,segment=int(q.segment_id),close=float(q.close),volume=float(q.volume),money=float(q.money),return_bp=float(q.log_return*10000)))
            p=b[b.period==period].copy();within=p.groupby('segment_id').cumcount().to_numpy();rr=p.log_return.to_numpy();vv=p.volume.to_numpy()
            masks={'all':np.isfinite(rr),'after_first_20_segment_bars':np.isfinite(rr)&(within>=20),'exclude_segment_terminal_bar':np.isfinite(rr)&np.r_[p.segment_id.to_numpy()[1:]==p.segment_id.to_numpy()[:-1],False]}
            for name,mask in masks.items():
                x=rr[mask];tailrows.append(dict(file=file,product=code,period=period,slice=name,n=len(x),excess_kurtosis=float(stats.kurtosis(x,bias=False)),diagnostic_only=name!='all'))
        print(n,code,'raw event evidence checked',flush=True)
    save('acf_segment_centering',acrows);save('raw_extreme_validation',rawrows);save('tail_session_sensitivity',tailrows);save('independent_filter_validation',filterchecks);save('event_price_context',events)

if __name__=='__main__':main()
