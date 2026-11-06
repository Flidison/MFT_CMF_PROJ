"""Hash the staged Git payload, excluding the manifest itself."""
from pathlib import Path
import csv,hashlib,io,subprocess
ROOT=Path(__file__).resolve().parents[1]

def main():
    raw=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT)
    entries=[]
    for record in raw.split(b'\0'):
        if not record:continue
        metadata,path=record.split(b'\t',1);mode,object_id,stage=metadata.split()
        assert stage==b'0' and mode in [b'100644',b'100755'],'Resolve conflicts or unsupported Git entries first'
        if path.decode()!='publication_manifest.csv':entries.append((path.decode(),object_id))
    request=b''.join(object_id+b'\n' for path,object_id in entries)
    response=subprocess.run(['git','cat-file','--batch'],input=request,stdout=subprocess.PIPE,check=True,cwd=ROOT).stdout
    stream=io.BytesIO(response);rows=[]
    for path,object_id in entries:
        header=stream.readline().split();assert header[0]==object_id and header[1]==b'blob'
        size=int(header[2]);body=stream.read(size);assert len(body)==size and stream.read(1)==b'\n'
        rows.append(dict(path=path,bytes=size,sha256=hashlib.sha256(body).hexdigest(),storage='git'))
    with (ROOT/'publication_manifest.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=['path','bytes','sha256','storage'],lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    print(f'Wrote checksums for {len(rows)} staged files; stage publication_manifest.csv before committing.')

if __name__=='__main__':main()
