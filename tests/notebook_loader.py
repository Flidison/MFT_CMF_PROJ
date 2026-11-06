"""Load actual notebook definitions without running data/output cells."""
import ast,json,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load_notebook(name):
    source_root=ROOT
    nb=json.loads((source_root/name).read_text());module=types.ModuleType('_mft_test_'+name.replace('.','_'));sys.modules[module.__name__]=module
    module.__dict__.update(ROOT=ROOT,RAW_FIELDS={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume','money':'Turnover','open_interest':'Open interest'},AVAILABLE_FEATURES=['Open','High','Low','Close','Volume','Turnover','Open interest','log_return'])
    trees=[ast.parse(''.join(c['source'])) for c in nb['cells'] if c['cell_type']=='code']
    for tree in trees:
        for n in tree.body:
            if isinstance(n,(ast.Import,ast.ImportFrom)):
                exec(compile(ast.Module(body=[n],type_ignores=[]),str(source_root/name),'exec'),module.__dict__)
            elif isinstance(n,ast.Assign):
                try:value=ast.literal_eval(n.value)
                except (ValueError,TypeError):continue
                for t in n.targets:
                    if isinstance(t,ast.Name):module.__dict__[t.id]=value
    for tree in trees:
        for n in tree.body:
            if isinstance(n,(ast.FunctionDef,ast.ClassDef)):
                exec(compile(ast.Module(body=[n],type_ignores=[]),str(source_root/name),'exec'),module.__dict__)
    return module
