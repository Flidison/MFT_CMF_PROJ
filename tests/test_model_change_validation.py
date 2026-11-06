import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest


@pytest.fixture(scope='module')
def validation():
    p=Path(__file__).resolve().parents[1]/'artifacts/research_54/audit_code/model_output_validation.py'
    spec=importlib.util.spec_from_file_location('model_change_validation',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_independent_future_matches_deterministic_affine_log_variance(validation):
    # With no stochastic shock load, the model has a known closed-form path.
    parameters=np.array([.05,0.,.8,0.]);next_log=np.array([.4,-.2]);scale=2.5
    got=validation.reference_future(next_log,parameters,scale,812)
    expected=scale**2*np.exp(.25+(next_log[:,None]-.25)*.8**np.arange(30))
    np.testing.assert_allclose(got,expected,rtol=1e-13)


def test_independent_next_log_restarts_at_gaps_and_contracts(validation):
    values=np.array([1.,2.,np.nan,3.,4.,5.]);segments=np.array([1,1,1,1,2,2])
    got=validation.reference_next_log(values,segments,0.,1.,np.array([.1,0.,.5,0.]))
    np.testing.assert_allclose(got,[.1,.15,np.nan,.1,.1,.15],equal_nan=True)


@pytest.mark.parametrize('corruption',['other_forecast','shape'])
def test_correction_allowance_rejects_unrelated_changes(validation,corruption):
    before=pd.DataFrame({'variance_V2_EGARCH_h5':[1.,2.],'variance_V1_GARCH_h5':[3.,4.]});after=before.copy()
    if corruption=='shape':after=after.iloc[:1]
    else:after.loc[0,'variance_V1_GARCH_h5']+=1
    with pytest.raises(AssertionError):validation.unchanged_except(before,after,validation.ALLOWED_FORECAST_COLUMNS)


def test_model_metric_allowance_rejects_other_models(validation):
    before=pd.DataFrame(dict(file=['X','X'],model=['V2_EGARCH','V1_GARCH'],loss=[1.,2.]));after=before.copy();after.loc[1,'loss']+=.01
    with pytest.raises(AssertionError):validation.assert_changed_rows_only(before,after,['file','model'],lambda key:key[1]=='V2_EGARCH')

@pytest.mark.parametrize('corruption',['value','order','dtype'])
def test_compact_baseline_rejects_value_order_or_dtype_change(validation,corruption):
    before=pd.DataFrame({'variance_V1_GARCH_h5':np.array([1.,2.]),'variance_V2_EGARCH_h5':[3.,4.]})
    record=dict(columns=list(before),rows=len(before),fingerprints={c:validation.column_fingerprint(before[c]) for c in before})
    after=before.copy()
    if corruption=='value':after.loc[0,'variance_V1_GARCH_h5']+=.001
    elif corruption=='order':after=after.iloc[::-1]
    else:after['variance_V1_GARCH_h5']=after.variance_V1_GARCH_h5.astype('float32')
    with pytest.raises(AssertionError):validation.unchanged_from_fingerprints(after,record,validation.ALLOWED_FORECAST_COLUMNS)
