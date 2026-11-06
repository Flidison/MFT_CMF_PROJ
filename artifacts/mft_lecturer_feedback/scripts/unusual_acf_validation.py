"""Independent direct checks of B/CY training squared-return volume sensitivity."""
from analyze_feedback import *

def main():
    saved=pd.read_csv(OUT/'tables/acf.csv');rows=[];pairrows=[]
    for code in ['B','CY']:
        path=next((SRC/'statistics/features').glob(code+'9999*'))
        b=pd.read_parquet(path);b=b[b.period=='train'].reset_index(drop=True)
        r=b.log_return.to_numpy();v=b.volume.to_numpy();s=b.segment_id.to_numpy()
        for lag in range(1,61):
            good=(s[lag:]==s[:-lag])&np.isfinite(r[lag:])&np.isfinite(r[:-lag]);vp=good&(v[lag:]>0)&(v[:-lag]>0)
            x,y=r[lag:]**2,r[:-lag]**2
            vals={name:direct_corr(x[mask],y[mask]) for name,mask in [('all',good),('positive_volume_pairs',vp)]}
            for name,mask in [('all',good),('positive_volume_pairs',vp)]:
                actual=saved[(saved['product']==code)&(saved.period=='train')&(saved.series=='sq_r')&(saved.lag==lag)&(saved['sample']==name)].iloc[0]
                assert actual.pairs==int(mask.sum()) and abs(actual.acf-vals[name])<1e-10
            rows.append(dict(product=code,period='train',lag=lag,all_pairs=int(good.sum()),positive_volume_pairs=int(vp.sum()),acf_all=vals['all'],acf_positive_volume=vals['positive_volume_pairs'],difference=vals['positive_volume_pairs']-vals['all'],independent_check_passed=True))
        selected=max([row for row in rows if row['product']==code],key=lambda row:abs(row['difference']))
        lag=selected['lag'];mask=(s[lag:]==s[:-lag])&np.isfinite(r[lag:])&np.isfinite(r[:-lag])&(v[lag:]>0)&(v[:-lag]>0)
        index=np.flatnonzero(mask)+lag;x=r[index]**2;y=r[index-lag]**2
        cross=(x-x.mean())*(y-y.mean())
        for rank,j in enumerate(np.argsort(np.abs(cross))[-10:][::-1],1):
            i=index[j];pairrows.append(dict(product=code,lag=lag,rank=rank,later_date=str(b.date.iloc[i]),earlier_date=str(b.date.iloc[i-lag]),symbol=b.symbol.iloc[i],later_return_bp=float(r[i]*10000),earlier_return_bp=float(r[i-lag]*10000),later_volume=float(v[i]),earlier_volume=float(v[i-lag]),absolute_centered_cross_product_share=float(abs(cross[j])/np.abs(cross).sum())))
    save('unusual_acf_volume_validation',rows);save('unusual_acf_influential_pairs',pairrows)
    print(pd.DataFrame(rows).assign(m=lambda x:abs(x.difference)).sort_values('m',ascending=False).groupby('product').head(1).to_string(index=False))

if __name__=='__main__':main()
