import numpy as np
import pandas as pd
import pytest
from notebook_loader import load_notebook

@pytest.fixture(scope='module')
def nb02():return load_notebook('02_research_statistics_features.ipynb')
@pytest.fixture(scope='module')
def nb07():return load_notebook('07_forecasting_models_54.ipynb')
@pytest.fixture(scope='module')
def nb08():return load_notebook('08_backtest_fees_risk_54.ipynb')

def market(n=160):
    rng=np.random.default_rng(37);p=100*np.exp(np.cumsum(rng.normal(0,.001,n)))
    return pd.DataFrame(dict(ID=np.arange(n),date=pd.date_range('2019-01-02 09:01',periods=n,freq='min'),symbol='X1905',open=p,high=p*1.002,low=p*.998,close=p,volume=np.ones(n),money=p*10,open_interest=100))

def test_features_exact_clock_nan_and_rolling(nb02):
    f=market();f.loc[50:,'date']+=pd.Timedelta(minutes=1);f.loc[90:,'symbol']='X1909';f.loc[120,'close']=np.nan
    a=nb02.build_segment_features(f);r=np.full(len(f),np.nan)
    for i in range(1,len(f)):
        if f.date[i]-f.date[i-1]==pd.Timedelta(minutes=1) and f.symbol[i]==f.symbol[i-1] and np.isfinite(f.close[i:i+1]).all() and np.isfinite(f.close[i-1]):r[i]=np.log(f.close[i]/f.close[i-1])
    np.testing.assert_allclose(a.log_return,r,atol=2e-15,equal_nan=True)
    for i in range(len(a)):
        expected=np.std(r[i-29:i+1],ddof=1) if i>=29 and a.segment_id[i]==a.segment_id[i-29] and np.isfinite(r[i-29:i+1]).all() else np.nan
        np.testing.assert_allclose(a.rolling_30m_volatility[i],expected,rtol=1e-11,atol=1e-15,equal_nan=True)

@pytest.mark.parametrize('lag',[-5,-1,0,1,5,500])
def test_fixed_lag_pairs_against_timestamp_reference(nb02,lag):
    rng=np.random.default_rng(3);x=rng.normal(size=70);y=rng.normal(size=70);x[7]=np.nan;y[10]=np.nan;s=np.repeat([1,2],35)
    a,b=nb02._pair_arrays(x,s,lag,y)
    expected=[]
    for i in range(len(x)):
        j=i-lag
        if 0<=j<len(x) and s[i]==s[j] and np.isfinite(x[i]) and np.isfinite(y[j]):expected.append((x[i],y[j]))
    actual=list(zip(a[np.isfinite(a)],b[np.isfinite(b)]));np.testing.assert_allclose(np.array(actual).reshape(-1,2),np.array(expected).reshape(-1,2))

@pytest.mark.parametrize('kind,params',[(0,[.05,.1,.1,.85]),(1,[-.02,.15,.9,-.08]),(2,[.05,.08,.16,.82])])
def test_variance_filter_against_scalar_reference(nb07,kind,params):
    x=np.array([np.nan,.1,-.2,.3,.5,np.nan,.2,-.3]);seg=np.array([1,1,1,1,2,2,2,2]);reset=np.r_[True,seg[1:]!=seg[:-1]];p=np.array(params)
    expected=np.full(len(x),np.nan);active=False
    for i in range(len(x)):
        if not np.isfinite(x[i]):active=False;continue
        if reset[i] or not active:h=1.
        elif kind==1:
            z=prev/np.sqrt(h);h=np.exp(np.clip(p[0]+p[2]*np.log(h)+p[1]*(abs(z)-np.sqrt(2/np.pi))+p[3]*z,-30,30))
        else:h=p[0]+p[3]*h+(p[1] if prev>=0 else p[2])*prev**2
        expected[i]=h;prev=x[i];active=True
    got=nb07.wf_variance_kernel(x,reset,p,kind)[0];np.testing.assert_allclose(got,expected,equal_nan=True)

@pytest.mark.parametrize('objective,point',[('model_garch_objective',[np.log(.05),0.,2.]),('wf_gjr_objective',[np.log(.05),0.,.3,2.]),('wf_egarch_objective',[-.02,.15,.9,-.08])])
def test_analytic_gradient_independent_difference(nb07,objective,point):
    rng=np.random.default_rng(12);x=rng.normal(size=600);reset=np.arange(600)%75==0;point=np.array(point);f=getattr(nb07,objective);analytic=f(point,x,reset)[1];numerical=[]
    for i in range(len(point)):
        step=np.zeros_like(point);step[i]=1e-5;numerical.append((f(point+step,x,reset)[0]-f(point-step,x,reset)[0])/2e-5)
    np.testing.assert_allclose(analytic,numerical,rtol=3e-4,atol=3e-5)

@pytest.mark.parametrize('h,delay',[(1,0),(5,0),(5,1),(30,0)])
def test_forecast_target_exact_future_window(nb02,nb07,h,delay):
    f=nb02.build_segment_features(market());target,rv=nb07.model_targets(f,h,delay,location=.0001)
    for i in np.flatnonzero(np.isfinite(target)):
        assert f.segment_id[i]==f.segment_id[i+h+delay]
        np.testing.assert_allclose(target[i],np.log(f.close[i+h+delay]/f.close[i+delay]),atol=1e-15)
        np.testing.assert_allclose(rv[i],np.mean((f.log_return.iloc[i+delay+1:i+delay+h+1]-.0001)**2),rtol=1e-12)

@pytest.mark.parametrize('notebook',['03_strategies_hypotheses.ipynb','07_forecasting_models_54.ipynb','08_backtest_fees_risk_54.ipynb'])
def test_egarch_fixed_horizon_against_direct_simulation(notebook):
    m=load_notebook(notebook);p=np.array([-.02,.15,.9,-.08]);horizon=30
    factors,powers=m.wf_egarch_factors({'parameters':p},horizon,np.random.default_rng(42))
    z=np.random.default_rng(42).standard_normal((m.EGARCH_SIMULATIONS//2,horizon));z=np.r_[z,-z]
    logh=np.full(len(z),.2);reference=[np.exp(logh).mean()]
    for j in range(horizon-1):
        logh=p[0]+p[2]*logh+p[1]*(np.abs(z[:,j])-np.sqrt(2/np.pi))+p[3]*z[:,j]
        reference.append(np.exp(logh).mean())
    np.testing.assert_allclose(np.exp(.2*powers)*factors,reference,rtol=1e-12)

@pytest.mark.parametrize('notebook',['03_strategies_hypotheses.ipynb','07_forecasting_models_54.ipynb','08_backtest_fees_risk_54.ipynb'])
def test_egarch_six_step_preserves_baseline_draws(notebook):
    m=load_notebook(notebook);p=np.array([-.02,.15,.9,-.08]);factors,powers=m.wf_egarch_factors({'parameters':p},6,np.random.default_rng(42));rng=np.random.default_rng(42);z=rng.standard_normal((m.EGARCH_SIMULATIONS//2,6));z=np.r_[z,-z];logh=np.full(len(z),.2);ref=[np.exp(logh).mean()]
    for j in range(5):logh=p[0]+p[2]*logh+p[1]*(np.abs(z[:,j])-np.sqrt(2/np.pi))+p[3]*z[:,j];ref.append(np.exp(logh).mean())
    np.testing.assert_allclose(np.exp(.2*powers)*factors,ref,rtol=1e-12)

@pytest.mark.parametrize('name',['V2_EGARCH','V3_GJR_GARCH'])
@pytest.mark.parametrize('notebook',['03_strategies_hypotheses.ipynb','07_forecasting_models_54.ipynb','08_backtest_fees_risk_54.ipynb'])
def test_zero_effective_likelihood_rejected(notebook,name):
    m=load_notebook(notebook);x=np.linspace(-1,1,1002);s=np.arange(len(x));fit=(m.wf_fit_volatility if notebook.startswith('03') else m.model_fit_volatility)(x,s,name)
    assert fit is None,'No within-run lag pairs exist; a successful fit with n=0 is undefined.'

@pytest.mark.parametrize('raw',['-3 CNY','bad3 CNY','3-4 CNY','-0.23‰','fee 0.23‰'])
def test_fee_parser_rejects_invalid_strings(nb08,raw):
    with pytest.raises(ValueError):nb08.parse_fee(raw,10000)

@pytest.mark.parametrize('raw,divisor,expected',[('3 CNY',None,(3.,0.)),('0 CNY',None,(0.,0.)),('0.23‰',10000,(0.,.000023)),('0.23‰',1000,(0.,.00023))])
def test_fee_units_exact_reference(nb08,raw,divisor,expected):np.testing.assert_allclose(nb08.parse_fee(raw,divisor),expected)

FEE=dict(open_fixed=3.,open_rate=.0001,close_today_fixed=1.,close_today_rate=.0002,close_previous_fixed=4.,close_previous_rate=.0003)
@pytest.mark.parametrize('side',[1.,-1.])
@pytest.mark.parametrize('same_day',[True,False])
@pytest.mark.parametrize('bp',[0.,.5,1.])
def test_accounting_independent_per_leg_reference(nb08,side,same_day,bp):
    q=side/(100*10);ep=101*(1+side*bp/10000);xp=103*(1-side*bp/10000);op=abs(q)*(3+ep*10*.0001);cl=abs(q)*((1 if same_day else 4)+xp*10*(.0002 if same_day else .0003));gross=q*10*2;slip=abs(q)*10*204*bp/10000;broker=abs(q)*.4
    r=nb08.account_trades(np.array([100.]),np.array([101.]),np.array([103.]),np.array([side]),10.,FEE,same_day,broker_cny=.2,slippage_bps=bp)
    for key,val in dict(quantity_per_capital=q,gross=gross,exchange_open=op,exchange_close=cl,broker=broker,slippage=slip,net=gross-op-cl-broker-slip,turnover=abs(q)*10*(ep+xp)).items():np.testing.assert_allclose(r[key],val,atol=1e-14)

def test_accounting_preserves_scalar_inputs(nb08):
    result=nb08.account_trades(100.,101.,103.,1.,10.,FEE)
    np.testing.assert_allclose(result['quantity_per_capital'],.001)
    np.testing.assert_allclose(result['net'],.02-.001*(3+1010*.0001+1+1030*.0002))

@pytest.mark.parametrize('signal,multiplier',[(1e300,1e300),(1e-300,1e-300)])
def test_accounting_rejects_unrepresentable_notional(nb08,signal,multiplier):
    with pytest.raises(ValueError):nb08.account_trades(signal,101.,103.,1.,multiplier,FEE)

@pytest.mark.parametrize('bad', ['signal_zero','entry_nan','multiplier_zero','position_nan','negative_fee','negative_broker','negative_slippage','huge_slippage'])
def test_invalid_accounting_inputs_rejected(nb08,bad):
    signal=np.array([100.]);entry=np.array([101.]);exit=np.array([103.]);pos=np.array([1.]);mult=10.;fee=FEE.copy();broker=0.;bp=0.
    if bad=='signal_zero':signal[0]=0
    elif bad=='entry_nan':entry[0]=np.nan
    elif bad=='multiplier_zero':mult=0
    elif bad=='position_nan':pos[0]=np.nan
    elif bad=='negative_fee':fee['open_rate']=-.01
    elif bad=='negative_broker':broker=-1
    elif bad=='negative_slippage':bp=-1
    else:bp=10000
    with pytest.raises(ValueError):nb08.account_trades(signal,entry,exit,pos,mult,fee,broker_cny=broker,slippage_bps=bp)

@pytest.mark.parametrize('values,level,expected',[([1,2,3,4],.5,3.5),([1,2,3],.5,8/3),([-2,0,5,10],.95,10.)])
def test_empirical_es_fractional_mass(nb08,values,level,expected):np.testing.assert_allclose(nb08.empirical_es(values,level),expected)
@pytest.mark.parametrize('values,level',[([],.95),([np.nan],.95),([1,2],1),([1,2],-.1)])
def test_invalid_empirical_es_rejected(nb08,values,level):
    with pytest.raises(ValueError):nb08.empirical_es(values,level)

@pytest.mark.parametrize('case',['normal','zero_entry','delayed','missing','contract','unresolved'])
def test_execution_chronology(nb08,case):
    t=np.arange(30,dtype=np.int64);c=np.zeros(30,np.int64);ok=np.ones(30,bool);v=np.ones(30);orig=np.array([0,6],np.int64);pos=np.ones(2)
    if case=='zero_entry':v[1]=0
    if case=='delayed':v[6:10]=0
    if case=='missing':t=t[t!=1];c=c[:len(t)];ok=ok[:len(t)];v=v[:len(t)]
    if case=='contract':c[3:]=1
    if case=='unresolved':v[6:]=0
    s,e,x=nb08.execute_orders(t,c,ok,v,orig,pos)
    if case=='normal':assert (s==1).all() and e[0]==1 and x[0]==6
    elif case=='zero_entry':assert s[0]==5 and e[0]==-1
    elif case=='delayed':assert x[0]==10 and s[1]==2
    elif case=='missing':assert s[0]==3
    else:assert s[0]==7 and e[0]==1
