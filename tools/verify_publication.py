"""Verify versioned publication files before regenerating notebook outputs."""
from pathlib import Path
import argparse,csv,hashlib
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args();root=args.root.resolve()
    records=list(csv.DictReader((root/'publication_manifest.csv').open()))
    failures=[]
    for record in records:
        path=(root/record['path']).resolve()
        if not path.is_relative_to(root):raise ValueError('Publication path escapes the checkout')
        if not path.is_file() or path.stat().st_size!=int(record['bytes']):
            failures.append(record['path']);continue
        with path.open('rb') as handle:digest=hashlib.file_digest(handle,'sha256').hexdigest()
        if digest!=record['sha256']:failures.append(record['path'])
    if failures:raise ValueError(f'Changed or missing publication files: {failures}')
    print(f'Validated {len(records)} versioned publication files.')

if __name__=='__main__':main()
