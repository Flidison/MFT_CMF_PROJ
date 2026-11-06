"""Focused regression tests against actual Notebook08 definitions, without executing its backtest."""
from pathlib import Path
import ast,json,hashlib
import numpy as np
import pandas as pd
from numba import njit

ROOT=Path.cwd();OUT=ROOT/'artifacts/research_54'; B=OUT/'backtest'
def main():
    nb=json.loads((ROOT/'08_backtest_fees_risk_54.ipynb').read_text())
    want={'execute_orders','valid_bars','account_trades','commission_per_lot','primary_common_mask','verified_fit_cache'}
    fields=['D0_Momentum5','D1_Raw_ARMA','D2_GARCH_ARMA','D2_EGARCH_ARMA','D2_GJR_ARMA','D3_Logistic_Core']+['variance_H_'+x for x in ['V1_GARCH','V2_EGARCH','V3_GJR_GARCH']]
    ns=dict(np=np,pd=pd,njit=njit,hashlib=hashlib,json=json,PRIMARY_COMMON_FIELDS=fields)
    for c in nb['cells']:
        if c['cell_type']!='code':continue
        tree=ast.parse(''.join(c['source']))
        selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in want]
        if selected:exec(compile(ast.Module(body=selected,type_ignores=[]),'<actual Notebook08 functions>','exec'),ns)
    rows=[]
    def passed(test,classification='regression'):rows.append(dict(check=test,status='passed',classification=classification))
    execute=ns['execute_orders'];account=ns['account_trades']
    tm=np.arange(30,dtype=np.int64);co=np.zeros(30,np.int64);ok=np.ones(30,bool);vol=np.ones(30)
    origins=np.array([0,6,12,18],np.int64);pos=np.ones(4)
    s,e,x=execute(tm,co,ok,vol,origins,pos)
    assert s.tolist()==[1,1,1,1] and np.array_equal(e,origins+1) and np.array_equal(x,e+5)
    passed('signal t -> entry t+1 -> planned exit t+6')
    for value in [0.,np.nan]:
        v=vol.copy();v[1]=value;s,e,x=execute(tm,co,ok,v,origins,pos)
        assert s[0]==5 and e[0]==-1
    passed('zero/unknown volume at entry cancels in the entry minute')
    v=vol.copy();v[6:10]=0.;s,e,x=execute(tm,co,ok,v,origins,pos)
    assert s[:2].tolist()==[1,2] and e[0]==1 and x[0]==10
    passed('delayed close retains open position and blocks overlapping orders')
    v=vol.copy();v[6:]=0.;s,e,x=execute(tm,co,ok,v,origins,pos)
    assert s[0]==7 and e[0]==1 and x[0]==-1 and (s[1:]==2).all()
    passed('future exit failure never cancels an already filled entry or frees its capital')
    c=co.copy();c[3:5]=1;c[5:]=2;s,e,x=execute(tm,c,ok,vol,origins,pos)
    assert s[0]==7
    passed('A -> B -> A symbol runs cannot bridge a contract change')
    c=co.copy();c[1:]=1;s,e,x=execute(tm,c,ok,vol,origins,pos);assert s[0]==6 and e[0]==-1
    passed('contract change between signal and entry cancels entry')
    use=tm!=1;s,e,x=execute(tm[use],co[use],ok[use],vol[use],np.array([0]),np.ones(1));assert s[0]==3
    passed('missing t+1 minute cannot jump to a later entry')
    s,e,x=execute(tm+1437,co,ok,vol,np.array([0]),np.ones(1));assert s[0]==7 and e[0]==1
    passed('calendar-midnight crossing remains explicitly unresolved')
    # Demonstrate rather than hide the calendar-date limitation.
    times=np.array([14*60,14*60+1,21*60+1],np.int64)
    s,e,x=execute(times,np.zeros(3,np.int64),np.ones(3,bool),np.ones(3),np.array([0]),np.ones(1))
    assert s[0]==1 and x[0]==2
    passed('same calendar date can allow a day-to-night exit; no official trading-day guarantee','documented limitation')
    frame=pd.DataFrame(dict(date=pd.date_range('2020-01-01',periods=4,freq='min'),open=[100]*4,high=[101,99,101,101],low=[99]*4,close=[100,100,-1,100]))
    assert ns['valid_bars'](frame).tolist()==[True,False,False,True]
    frame.loc[3,'date']=frame.loc[0,'date'];assert not ns['valid_bars'](frame).any()
    passed('invalid OHLC, nonpositive prices and both duplicate timestamps are non-executable')
    fee=dict(open_fixed=3.,open_rate=.0001,close_today_fixed=1.,close_today_rate=.0002,close_previous_fixed=4.,close_previous_rate=.0003)
    for side in [1.,-1.]:
        for same_day in [True,False]:
            for bp in [0.,.5,1.]:
                q=side/(100*10); ep=101*(1+side*bp/10000);xp=103*(1-side*bp/10000)
                op=abs(q)*(3+ep*10*.0001);cl=abs(q)*((1 if same_day else 4)+xp*10*(.0002 if same_day else .0003))
                slip=abs(q)*10*(101+103)*bp/10000;gross=q*10*(103-101)
                result=account(np.array([100.]),np.array([101.]),np.array([103.]),np.array([side]),10,fee,same_day,broker_cny=.2,slippage_bps=bp)
                for name,value in dict(quantity_per_capital=q,gross=gross,exchange_open=op,exchange_close=cl,broker=abs(q)*.4,slippage=slip,net=gross-op-cl-abs(q)*.4-slip,turnover=abs(q)*10*(ep+xp)).items():
                    np.testing.assert_allclose(result[name],[value],rtol=1e-12,atol=1e-14)
    passed('independent long/short fixed+ratio accounting: 12 close-today/previous and slippage combinations')
    d=pd.DataFrame({k:[1.,1.] for k in fields});d['breakout']=[np.nan,1.];d['D3_Logistic_Asymmetric']=[np.nan,1.]
    assert ns['primary_common_mask'](d).tolist()==[True,True]
    d.loc[1,'D3_Logistic_Core']=np.nan;assert ns['primary_common_mask'](d).tolist()==[True,False]
    passed('common S0-S9 excludes unused dependencies and preserves required NaNs')
    rec=json.loads((OUT/'statistics/manifest.json').read_text())['features'][0]
    mm=json.loads((OUT/'models/manifest.json').read_text());cache=json.loads((OUT/'models/by_file'/(Path(rec['file']).stem+'.json')).read_text())
    ns['verified_fit_cache'](cache,rec,mm)
    for changed in [dict(rec,sha256='changed'),dict(rec,file='wrong.csv')]:
        try:ns['verified_fit_cache'](cache,changed,mm)
        except AssertionError:pass
        else:raise AssertionError('Mismatched cache accepted')
    passed('fit-cache fingerprint rejects changed feature bytes and wrong instrument')
    assert 'runtime_constants' in mm['config']
    changed=json.loads(json.dumps(mm));changed['config']['runtime_constants']['expansion_window']+=1
    try:ns['verified_fit_cache'](cache,rec,changed)
    except AssertionError:pass
    else:raise AssertionError('Changed runtime window incorrectly reused the old fit cache')
    passed('07 runtime-window changes invalidate a previously valid cache fingerprint')
    pd.DataFrame(rows).to_csv(OUT/'audit_regression_tests.csv',index=False)
    print(pd.DataFrame(rows).to_string(index=False))
if __name__=='__main__':main()
