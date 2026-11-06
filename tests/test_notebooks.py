"""Check notebook structure, syntax and saved execution state."""
from pathlib import Path
import ast,re
import nbformat
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('path',sorted(ROOT.glob('0[1-8]_*.ipynb')),ids=lambda p:p.name)
def test_notebook_schema_execution_and_english_text(path):
    notebook=nbformat.read(path,as_version=4);nbformat.validate(notebook)
    for index,cell in enumerate(notebook.cells,1):
        assert not re.search(r'[\u0400-\u04ff]',cell.source),f'Non-English source: {path.name}, cell {index}'
        if cell.cell_type=='code':
            ast.parse(cell.source)
            assert cell.execution_count is not None,f'Unexecuted cell: {path.name}, {index}'
            for output in cell.get('outputs',[]):
                assert output.output_type!='error',f'Execution error: {path.name}, {index}'
                text=output.get('text','') if output.output_type=='stream' else '\n'.join(str(v) for k,v in output.get('data',{}).items() if k.startswith('text/'))
                assert not re.search(r'[\u0400-\u04ff]',text),f'Non-English output: {path.name}, cell {index}'
