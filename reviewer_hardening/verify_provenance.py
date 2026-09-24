#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,re,sys
p=Path(__file__).with_name('architecture_provenance.json')
d=json.loads(p.read_text(encoding='utf-8'))
assert d['schema']=='architecture-provenance-v1'
ids=set()
assert len(d['sources']) >= 7, 'expected at least seven source-anchor records'
for s in d['sources']:
    assert s['source_id'] not in ids; ids.add(s['source_id'])
    assert re.fullmatch(r'[0-9a-f]{40}',s['commit'])
    assert s['repository'].startswith('https://github.com/')
    assert s['retrieval_date']=='2026-09-20'
    assert s['files'], f"{s['source_id']}: no source anchors"
    for f in s['files']:
        assert re.fullmatch(r'[0-9a-f]{64}',f['sha256'])
        assert isinstance(f['anchor_line'],int) and f['anchor_line']>0
print(json.dumps({'status':'PASS','source_records':len(d['sources']),'anchored_files':sum(len(s['files']) for s in d['sources'])},sort_keys=True))
