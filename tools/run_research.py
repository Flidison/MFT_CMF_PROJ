"""Execute research notebooks in separate kernels from the repository root.

Use an isolated copy: outputs and executed notebook cells are written in place.
Install requirements.txt and requirements-validation.txt first.
"""
from pathlib import Path
import argparse,json,time,os,sys,traceback,hashlib
import nbformat
from nbclient import NotebookClient
from jupyter_client.kernelspec import KernelSpecManager
P=Path(__file__).resolve().parents[1];O=P/'audit_reports/pre_handoff_2026-11-06';logs=O/'execution';logs.mkdir(exist_ok=True)
a=argparse.ArgumentParser();a.add_argument('notebooks',nargs='+');a.add_argument('--python',default=sys.executable);args=a.parse_args()
ksdir=O/'kernel_spec'/'mft-handoff';ksdir.mkdir(parents=True,exist_ok=True)
(ksdir/'kernel.json').write_text(json.dumps({'argv':[args.python,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'MFT handoff isolated','language':'python','env':{'PYTHONDONTWRITEBYTECODE':'1','MPLBACKEND':'module://matplotlib_inline.backend_inline','MPLCONFIGDIR':str(O/'mpl_config'),'NUMBA_CACHE_DIR':str(O/'numba_cache'),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MFT_PROJECT_ROOT':str(P)}}))
ksm=KernelSpecManager(kernel_dirs=[str(ksdir.parent)])
for name in args.notebooks:
 p=P/name;nb=nbformat.read(p,as_version=4);nbformat.validate(nb);started=time.time();record={'notebook':name,'python':args.python,'started':started,'status':'running','cells':[], 'input_notebook_sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'source_sha256':hashlib.sha256('\n'.join(c.source for c in nb.cells if c.cell_type=='code').encode()).hexdigest()}
 def cell_start(cell,cell_index):
  record['cells'].append({'index':cell_index,'started':time.time(),'source_first_line':cell.source.splitlines()[0] if cell.source else ''});(logs/(p.stem+'.status.json')).write_text(json.dumps(record,indent=2));print(f'{name}:cell{cell_index+1}',flush=True)
 client=NotebookClient(nb,timeout=7200,kernel_name='mft-handoff',resources={'metadata':{'path':str(P)}},allow_errors=False,on_cell_start=cell_start)
 from jupyter_client import KernelManager
 client.km=KernelManager(kernel_name='mft-handoff',kernel_spec_manager=ksm)
 try:
  client.execute();nbformat.validate(nb);nbformat.write(nb,p);record.update(status='passed',seconds=time.time()-started);print(name,'PASSED',record['seconds'],flush=True)
 except Exception as e:
  record.update(status='failed',seconds=time.time()-started,error=type(e).__name__,message=str(e));nbformat.write(nb,logs/(p.stem+'.failed.ipynb'));traceback.print_exc()
  (logs/(p.stem+'.status.json')).write_text(json.dumps(record,indent=2));raise
 (logs/(p.stem+'.status.json')).write_text(json.dumps(record,indent=2))
