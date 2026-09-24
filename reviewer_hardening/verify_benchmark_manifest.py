#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys
HERE=Path(__file__).resolve().parent; A=HERE.parent
d=json.loads((HERE/'benchmark_file_manifest.json').read_text())
assert d['schema']=='benchmark-file-manifest-v1'
seen=set()
for r in d['files']:
    assert r['path'] not in seen; seen.add(r['path'])
    p=A/r['path']; assert p.is_file(),r['path']
    assert p.stat().st_size==r['bytes'],r['path']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],r['path']
assert len(seen)==d['total_files']
print(json.dumps({'status':'PASS','files':len(seen),'counts':d['counts']},sort_keys=True))
