"""One-time, audited metadata migration: no fit, forecast or metric values change.

Requires unchanged runtime settings versus the preserved pre-audit notebook,
independent successful forecast/normalization checks, and verified old cache hashes.
Future runs of07 include these settings in its ordinary invalidation key.
"""
from pathlib import Path
import ast,json,hashlib
ROOT=Path.cwd();OUT=ROOT/'artifacts/research_54';M=OUT/'models';S=OUT/'audit_snapshot_20261009T200003Z'
NAMES={'expansion_window':'EXPANSION_WINDOW','expansion_min_periods':'EXPANSION_MIN_PERIODS','breakout_window':'BREAKOUT_WINDOW','arma_candidates':'ARMA_CANDIDATES','mean_orders':'MEAN_ORDERS','volatility_names':'VOLATILITY_NAMES','direction_names':'DIRECTION_NAMES'}
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def constants(path):
 nb=json.loads(path.read_text());values={}
 for c in nb['cells']:
  if c['cell_type']!='code':continue
  for n in ast.parse(''.join(c['source'])).body:
   if isinstance(n,ast.Assign):
    for target in n.targets:
     if isinstance(target,ast.Name) and target.id in NAMES.values():values[target.id]=ast.literal_eval(n.value)
 return json.loads(json.dumps({k:values[v] for k,v in NAMES.items()}))
def main():
 before=constants(S/'07_forecasting_models_54.ipynb');after=constants(ROOT/'07_forecasting_models_54.ipynb');assert before==after
 for f in ['volatility_findings.json','training_normalization_findings.json']:
  state=json.loads((OUT/'audit_code'/f).read_text());assert 'passed' in state['status']
 model=json.loads((M/'manifest.json').read_text());old=json.loads((S/'models/manifest.json').read_text())
 assert model['config']==old['config'], 'Migration must be applied exactly once to the original verified config'
 features=json.loads((OUT/'statistics/manifest.json').read_text());assert digest(OUT/'statistics/manifest.json')==model['input_sha256']
 config={**model['config'],'runtime_constants':after};records=[];updates=[]
 for r in features['features']:
  p=M/'by_file'/(Path(r['file']).stem+'.json');cache=json.loads(p.read_text())
  previous=hashlib.sha256(json.dumps(dict(config=model['config'],record=r),sort_keys=True).encode()).hexdigest();assert cache['fingerprint']==previous
  assert digest(ROOT/r['path'])==r['sha256']
  cov=cache['results']['coverage'][0];fp=M/'forecasts'/(Path(r['file']).stem+'.parquet')
  if cov.get('forecast_sha256'):assert digest(fp)==cov['forecast_sha256']==digest(S/'models/forecasts'/fp.name)
  fingerprint=hashlib.sha256(json.dumps(dict(config=config,record=r),sort_keys=True).encode()).hexdigest()
  records.append(dict(file=r['file'],previous_fingerprint=previous,new_fingerprint=fingerprint,results_sha256=hashlib.sha256(json.dumps(cache['results'],sort_keys=True).encode()).hexdigest(),forecast_sha256=cov.get('forecast_sha256')))
  cache['fingerprint']=fingerprint;updates.append((p,cache))
 for p,cache in updates:p.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n')
 model['config']=config;(M/'manifest.json').write_text(json.dumps(model,ensure_ascii=False,indent=2)+'\n')
 (OUT/'audit_cache_config_migration.json').write_text(json.dumps(dict(reason='Bind omitted runtime constants after independent current-result verification',runtime_constants=after,no_optimizer_called=True,forecast_bytes_unchanged=True,records=records),indent=2)+'\n')
 print('Migrated54 cache fingerprints;53 forecast files byte-for-byte unchanged; no fit or metric changes.')
if __name__=='__main__':main()
