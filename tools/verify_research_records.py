#!/usr/bin/env python3
"""Validate the claim/evidence and external-resource ledgers without network access."""
from pathlib import Path
import csv, json, re, sys
ROOT=Path(__file__).resolve().parents[1]

def find_one(name):
    xs=[p for p in ROOT.rglob(name) if '.git' not in p.parts]
    if len(xs)!=1: raise SystemExit(f'expected exactly one {name}, found {len(xs)}: {xs}')
    return xs[0]
def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def pick(row,*names):
    low={k.lower().strip():str(v or '').strip() for k,v in row.items()}
    for n in names:
        if n in low: return low[n]
    return ''
def main():
    cp=find_one('claim_evidence_ledger.csv'); ep=find_one('external_resources.csv')
    claims=rows(cp); ext=rows(ep); errors=[]
    if len(claims)!=21: errors.append(f'expected 21 claim-ledger rows, found {len(claims)}')
    if len(ext)!=36: errors.append(f'expected 36 external-resource rows, found {len(ext)}')
    ids=[]
    for i,r in enumerate(claims,2):
        rid=pick(r,'claim_id','id','claim'); statement=pick(r,'claim','statement','claim_text','description'); evidence=pick(r,'evidence','evidence_location','artifact','source','support')
        if not rid: errors.append(f'{cp.name}:{i}: missing claim identifier')
        else: ids.append(rid)
        if not statement: errors.append(f'{cp.name}:{i}: missing claim text')
        if not evidence: errors.append(f'{cp.name}:{i}: missing evidence locator')
    if len(set(ids))!=len(ids): errors.append('duplicate claim identifiers')
    extids=[]; urls=[]
    for i,r in enumerate(ext,2):
        rid=pick(r,'resource_id','id','name','resource'); title=pick(r,'title','resource_title','name'); url=pick(r,'url','source_url','location','uri'); date=pick(r,'accessed','access_date','retrieved','retrieved_on','date')
        if not rid: errors.append(f'{ep.name}:{i}: missing resource identifier')
        else: extids.append(rid)
        if not title: errors.append(f'{ep.name}:{i}: missing title')
        if not url or not url.startswith('https://'): errors.append(f'{ep.name}:{i}: missing/non-HTTPS URL')
        else: urls.append(url)
        if date and not re.fullmatch(r'20\d\d-\d\d-\d\d',date): errors.append(f'{ep.name}:{i}: non-ISO date {date!r}')
        modified=pick(r,'modified','locally_modified','modification','status').lower()
        if modified in {'yes','true','1','modified'}: errors.append(f'{ep.name}:{i}: resource marked modified without a separate derived-resource record')
    if len(set(extids))!=len(extids): errors.append('duplicate external-resource identifiers')
    if len(set(urls))!=len(urls): errors.append('duplicate external-resource URLs')
    audits=[p for p in ROOT.rglob('external-resource-live-audit.json') if '.git' not in p.parts]
    if len(audits)!=1:
        errors.append(f'expected one frozen external-resource live audit, found {len(audits)}')
    else:
        import json
        try:
            live=json.loads(audits[0].read_text(encoding='utf-8'))
            lrecords=live.get('records',[])
            if live.get('resource_count')!=36 or len(lrecords)!=36: errors.append('live URL audit does not contain 36 records')
            if live.get('broken')!=0 or any(r.get('classification')=='broken' for r in lrecords): errors.append('live URL audit contains broken resources')
            lurls={r.get('url','') for r in lrecords}
            if lurls!=set(urls): errors.append('live URL audit URL set differs from external_resources.csv')
        except Exception as exc: errors.append(f'invalid live URL audit: {exc}')
    if errors: raise SystemExit('RESEARCH-RECORD AUDIT FAILED\n- '+'\n- '.join(errors))
    print(json.dumps({'status':'PASS','claims':len(claims),'external_resources':len(ext),'claim_ledger':str(cp.relative_to(ROOT)),'external_ledger':str(ep.relative_to(ROOT))},sort_keys=True))
if __name__=='__main__': main()
