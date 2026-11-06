"""Exercise the actual 07 collection cell, not a copy of its serialization logic."""
import ast,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from notebook_loader import load_notebook, ROOT


def test_fresh_and_warm_cache_export_identical_full_precision_csv(tmp_path):
    import os
    source=ROOT/'07_forecasting_models_54.ipynb'
    if os.environ.get('MFT_TEST_BASELINE'):
        source=ROOT/'audit_reports/pre_handoff_2026-11-06/baseline'/source.name
    nb=json.loads(source.read_text());code=''.join(nb['cells'][18]['source'])
    code=code[code.index('parts={'):]
    module=load_notebook('07_forecasting_models_54.ipynb');ns=vars(module).copy()
    data=tmp_path/'input';data.write_bytes(b'fixed input')
    records=[dict(file=f'X{i:02}.csv',path='input',sha256=hashlib.sha256(data.read_bytes()).hexdigest()) for i in range(54)]
    out=tmp_path/'models';(out/'by_file').mkdir(parents=True);(out/'forecasts').mkdir()
    coefficient=np.array([.12345678901234567,-.9876543210987654])
    calls=[]
    def fit(record,number):
        calls.append(record['file'])
        return dict(coverage=[dict(file=record['file'],status='eligible')],
            fits=[dict(file=record['file'],order=(1,0),parameters=coefficient.copy())],
            mean=[],variance=[],direction=[],calibration=[],regimes=[],numerics=[])
    ns.update(ROOT=tmp_path,OUT=out,manifest={'features':records},files=[r['file'] for r in records],
        config={'test':'serialization'},REUSE_VERIFIED_CACHE=True,model_process_file=fit)
    exec(compile(code,'<actual 07 cache collection cell>','exec'),ns)
    first=(out/'fits.csv').read_bytes();assert len(calls)==54
    exec(compile(code,'<actual 07 cache collection cell>','exec'),ns)
    assert len(calls)==54,'The warm run must actually read caches.'
    assert (out/'fits.csv').read_bytes()==first,'Fresh/cache paths must export the same containers and precision.'
    exported=pd.read_csv(out/'fits.csv')
    np.testing.assert_array_equal(ast.literal_eval(exported.parameters.iloc[0]),coefficient)
    assert ast.literal_eval(exported.order.iloc[0])==[1,0]
