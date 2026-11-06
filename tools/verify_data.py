"""Verify unchanged raw inputs and, optionally, downloaded release archives."""
from pathlib import Path
import argparse,csv,hashlib,json

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    with path.open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--archives',type=Path)
    parser.add_argument('--archives-only',action='store_true')
    args=parser.parse_args()
    if args.archives:
        release=json.loads((ROOT/'release_manifest.json').read_text())
        entries=[r for r in release['archives'] if r['name'].startswith('raw-data-')]
        for entry in entries:
            path=args.archives/entry['name']
            if not path.is_file() or sha(path)!=entry['sha256']:raise ValueError(f'Archive missing or checksum mismatch: {path}')
        print(f'Validated {len(entries)} raw-data release archives.')
    if not args.archives_only:
        records=list(csv.DictReader((ROOT/'data/raw_manifest.csv').open()))
        for record in records:
            path=args.root/record['path']
            if not path.is_file() or path.stat().st_size!=int(record['bytes']) or sha(path)!=record['sha256']:
                raise ValueError(f'Raw input missing or changed: {path}')
        print(f'Validated all {len(records)} raw CSV files.')

if __name__=='__main__':main()
