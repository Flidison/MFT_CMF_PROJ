"""Independent scalar/matrix references, without executing notebook I/O cells."""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from notebook_loader import load_notebook


@pytest.mark.parametrize('name',['03_strategies_hypotheses.ipynb','07_forecasting_models_54.ipynb','08_backtest_fees_risk_54.ipynb'])
def test_arma_reset_against_scalar_reference(name):
    module=load_notebook(name)
    x=np.array([.2,.3,-.1,.4,np.nan,.7,-.3,.2,.5,.1])
    reset=np.array([True,False,False,False,False,False,False,False,True,False])
    expected=np.full(len(x),np.nan);history=[];errors=[];likelihood=[]
    for i,current in enumerate(x):
        if reset[i] or not np.isfinite(current):history=[];errors=[]
        if not np.isfinite(current):continue
        error=current-.3*history[-1]+.1*history[-2]-.2*errors[-1] if len(history)>=2 else 0.
        expected[i]=error
        if len(history)>=2:likelihood.append(error**2)
        history.append(current);errors.append(error)
    got,mse,n=module.wf_arma_kernel(x,reset,.3,-.1,.2)
    np.testing.assert_allclose(got,expected,equal_nan=True)
    assert n==len(likelihood)
    np.testing.assert_allclose(mse,np.mean(likelihood))


def test_acf_and_hac_against_dense_bartlett_matrix():
    module=load_notebook('05_research_statistics_features_54.ipynb')
    rng=np.random.default_rng(118);values=rng.normal(size=600)
    segments=np.repeat(np.arange(100),6);days=np.repeat(np.arange(100),6);lag=2
    got=module.acf_row(values,segments,days,lag)
    pairs=[(i,i-lag) for i in range(lag,len(values)) if segments[i]==segments[i-lag]]
    a=np.array([values[i] for i,j in pairs]);b=np.array([values[j] for i,j in pairs])
    rho=np.corrcoef(a,b)[0,1];np.testing.assert_allclose(got['acf'],rho,atol=1e-15)
    u=(a-a.mean())/a.std();v=(b-b.mean())/b.std()
    influence=u*v-.5*rho*(u*u+v*v)
    score=np.array([sum(z for (i,j),z in zip(pairs,influence) if days[i]==day) for day in range(100)])
    distance=np.abs(np.arange(100)[:,None]-np.arange(100)[None,:])
    for bandwidth in [20,60]:
        weight=np.maximum(1-distance/(bandwidth+1),0)
        reference=np.sqrt(score@weight@score*100/99)/len(pairs)
        np.testing.assert_allclose(got[f'se_hac{bandwidth}'],reference,rtol=1e-13)


def ledger():
    gross=np.array([.02,-.01,.005,0.,-.003]);cost=np.array([.001,.002,.001,0.,.001])
    return pd.DataFrame(dict(gross=gross,net=gross-cost,costs=cost,exchange_open=cost/2,
        exchange_close=cost/2,broker=np.zeros(5),slippage=np.zeros(5)))


def test_portfolio_metrics_against_scalar_capital_account():
    module=load_notebook('08_backtest_fees_risk_54.ipynb');daily=ledger();result=module.performance(daily,{})
    capital=1.;high=1.;mdd=0.;gross_contribution=0.;cost_contribution=0.
    for row in daily.itertuples():
        gross_contribution+=capital*row.gross;cost_contribution+=capital*row.costs
        capital*=1+row.net;high=max(high,capital);mdd=max(mdd,1-capital/high)
    np.testing.assert_allclose(result['total_return'],capital-1,atol=1e-15)
    np.testing.assert_allclose(result['maximum_drawdown'],mdd,atol=1e-15)
    np.testing.assert_allclose(result['gross_contribution'],gross_contribution)
    np.testing.assert_allclose(result['costs_contribution'],cost_contribution)
    x=daily.net.to_numpy();variance=sum((z-x.mean())**2 for z in x)/(len(x)-1)
    np.testing.assert_allclose(result['sharpe'],x.mean()/np.sqrt(variance)*np.sqrt(365.25))
    np.testing.assert_allclose(result['daily_var95'],np.quantile(-x,.95))
    np.testing.assert_allclose(result['daily_es95'],max(-x))


@pytest.mark.parametrize('case',['empty','nan','inconsistent'])
def test_performance_rejects_invalid_ledger(case):
    module=load_notebook('08_backtest_fees_risk_54.ipynb');daily=ledger()
    if case=='empty':daily=daily.iloc[:0]
    elif case=='nan':daily.loc[0,'net']=np.nan
    else:daily.loc[0,'net']+=.01
    with pytest.raises(ValueError):module.performance(daily,{})


@pytest.mark.parametrize('case',['absent','equal','different'])
def test_source_comparison_claim_matches_evidence(tmp_path,case):
    path=Path(__file__).resolve().parents[1]/'artifacts/research_54/audit_code/fee_audit.py'
    spec=importlib.util.spec_from_file_location('fee_audit',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original=tmp_path/'original';copy=tmp_path/'copy';copy.write_bytes(b'source')
    if case!='absent':original.write_bytes(b'source' if case=='equal' else b'other')
    exists,matches,statement=module.original_copy_evidence(original,copy)
    assert exists==(case!='absent')
    assert matches==({'absent':None,'equal':True,'different':False}[case])
    if case=='absent':assert 'not performed' in statement
    elif case=='different':assert 'differs' in statement
    else:assert 'matches' in statement
