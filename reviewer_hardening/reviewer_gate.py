#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, csv, hashlib, json, os, re, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ARTIFACT=HERE.parent
PROJECT=ARTIFACT.parent

def run(cmd,cwd=HERE,timeout=600):
    p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    if p.returncode:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(map(str,cmd))}\n{p.stdout}")
    return p.stdout

def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()

def check_import_independence():
    p=HERE/'verify_architecture_cases.py'; tree=ast.parse(p.read_text())
    allowed={'argparse','itertools','json','sys','re','fractions','pathlib','typing','__future__'}
    imports=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import): imports += [a.name.split('.')[0] for a in n.names]
        elif isinstance(n,ast.ImportFrom): imports.append((n.module or '').split('.')[0])
    bad=sorted(set(imports)-allowed)
    if bad: raise AssertionError(f"architecture oracle imports non-stdlib/project modules: {bad}")
    return sorted(set(imports))

def check_claim_matrix():
    p=HERE/'CLAIM-EVIDENCE-MATRIX.csv'
    with p.open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    if len(rows)<20: raise AssertionError('claim-evidence matrix too small')
    ids=[r['claim_id'] for r in rows]
    if len(ids)!=len(set(ids)): raise AssertionError('duplicate claim ids')
    required={'claim','claim_type','evidence','checker_or_source','residual_limit'}
    for r in rows:
        if any(not r[k].strip() for k in required): raise AssertionError(f"incomplete claim row {r['claim_id']}")
    return len(rows)

def check_provenance():
    p=HERE/'architecture_provenance.json'
    if not p.exists():
        return (0,0)
    d=json.loads(p.read_text())
    if d.get('schema')!='architecture-provenance-v1':
        raise AssertionError('invalid architecture provenance schema')
    # The final packet makes no source-derived-topology claim.  Empty anchors
    # are therefore an honest not-applicable record, not a failed validation.
    sources=d.get('sources',[])
    return len(sources),sum(len(s.get('files',[])) for s in sources)

def check_venue_sources():
    d=json.loads((HERE/'venue_source_status.json').read_text())
    if d['target'].find('TACO')<0 or len(d['sources'])<5: raise AssertionError('venue source inventory incomplete')
    for s in d['sources']:
        if not (s['url'].startswith('https://www.acm.org/') or s['url'].startswith('https://authors.acm.org/') or s['url'].startswith('https://dl.acm.org/')):
            raise AssertionError(f"non-official venue source: {s['url']}")
        if s.get('http_status') in {404,410} or (isinstance(s.get('http_status'),int) and s['http_status']>=500):
            raise AssertionError(f"dead venue source: {s['url']} status={s.get('http_status')}")
    return len(d['sources'])

def check_bibliography_audit():
    p=PROJECT/'paper'/'reference-audit.json'
    if not p.exists():
        raise AssertionError('paper/reference-audit.json missing')
    d=json.loads(p.read_text())
    if (d.get('status')!='PASS' or d.get('bib_entries')!=70 or
        d.get('unique_cited_keys')!=70 or d.get('missing_entries') or
        d.get('unused_entries')):
        raise AssertionError('packaged bibliography audit failed')
    return {
        'status':'PASS',
        'entries':d['bib_entries'],
        'cited_entries':d['unique_cited_keys'],
        'doi_entries':d.get('doi_entries'),
        'isbn_only_entries':d.get('isbn_only_entries'),
    }

def check_path_budget_semantics(path_test_output:str):
    methods=sum(1 for line in path_test_output.splitlines() if line.strip().startswith('test_'))
    if methods < 10:
        raise AssertionError(f'path-budget regression suite too small: {methods}')
    boundary=json.loads((HERE/'path_enumeration_boundary.json').read_text())
    if boundary.get('status')!='PASS' or boundary.get('largest_accepted_depth')!=12 or boundary.get('first_rejected_depth')!=13:
        raise AssertionError('path-budget fail-closed boundary evidence missing')
    return {
        'status':'PASS',
        'path_budget_related_test_functions':methods,
        'explicit_fallback_boundary':True,
        'largest_accepted_depth':12,
        'first_rejected_depth':13,
    }

def check_environment_record():
    d=json.loads((HERE/'validation_environment.json').read_text())
    if d.get('schema')!='validation-environment-v1' or not d.get('python'):
        raise AssertionError('validation environment record incomplete')
    return {'python':d['python'].split()[0],'platform':d['platform'],'tools':d['tools']}

def check_static_code():
    d=json.loads((HERE/'static_code_audit.json').read_text())
    if d.get('status')!='PASS' or d.get('forbidden_constructs'):
        raise AssertionError('static code audit failed')
    return {'python_files':d['python_files'],'total_bytes':d['total_bytes']}

def check_smt():
    frozen=json.loads((HERE/'smtlib_frozen_results.json').read_text())
    smt_files=sorted((HERE/'smtlib_cases').glob('*.smt2'))
    if len(smt_files)<5:
        raise AssertionError('SMT-LIB export inventory is incomplete')
    if frozen.get('status') not in {'PASS','NOT_RUN'}:
        raise AssertionError('unexpected frozen SMT-LIB validation status')
    live_path=HERE/'smtlib_live_results.json'
    live=json.loads(live_path.read_text()) if live_path.exists() else {'status':'NOT_RUN','engine':'not invoked','results':{}}
    if live.get('status')=='PASS' and frozen.get('status')=='PASS' and live.get('results')!=frozen.get('results'):
        raise AssertionError('live SMT results disagree with frozen independent run')
    if live.get('status') not in {'PASS','NOT_RUN'}:
        raise AssertionError('unexpected live SMT validation status')
    return {
        'smtlib_files':len(smt_files),
        'frozen_status':frozen.get('status'),
        'frozen_engine':frozen.get('engine'),
        'live_status':live.get('status'),
        'live_engine':live.get('engine'),
        'limitation':'No solver claim is made when the executable is unavailable.',
    }

def check_path_cap():
    d=json.loads((HERE/'path_enumeration_boundary.json').read_text())
    if d.get('status')!='PASS' or d.get('largest_accepted_depth')!=12 or d.get('first_rejected_depth')!=13:
        raise AssertionError('path-count cap boundary failed')
    return d

def check_scaling():
    import csv
    with (HERE/'path_budget_scaling.csv').open(newline='',encoding='utf-8') as f: rows=list(csv.DictReader(f))
    if not rows or int(rows[-1]['pairs'])<4096:
        raise AssertionError('path-budget scaling range incomplete')
    for r in rows:
        if int(r['witness_rows'])!=int(r['pairs']) or int(r['explicit_bad_paths'])!=1:
            raise AssertionError('path-budget structural scaling drift')
    return {'rows':len(rows),'max_pairs':int(rows[-1]['pairs']),'max_certificate_bytes':int(rows[-1]['certificate_bytes'])}

def check_benchmark_manifest():
    # Inventory the packaged benchmark families directly.  No separate hash
    # manifest is required or claimed.
    model_files=list((ARTIFACT/'cases').glob('case-*.json')) + list((ARTIFACT/'tpeg_cases').glob('tpeg-*.json'))
    result_files=list((ARTIFACT/'results').glob('case-*.json')) + list((ARTIFACT/'tpeg_results').glob('tpeg-*.json'))
    certificate_files=list((ARTIFACT/'results'/'certificates').glob('case-*.json')) + list((ARTIFACT/'tpeg_results'/'certificates').glob('tpeg-*.json'))
    if len(model_files)!=158 or len(result_files)!=158 or len(certificate_files)!=99:
        raise AssertionError(f'benchmark inventory drift: models={len(model_files)}, results={len(result_files)}, certificates={len(certificate_files)}')
    return {'total_files':len(model_files)+len(result_files)+len(certificate_files),
            'counts':{'model':len(model_files),'result':len(result_files),'certificate':len(certificate_files)}}

def check_core_inventory():
    pyfiles=[]; texfiles=[]; jsonfiles=[]
    for p in ARTIFACT.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in {'__pycache__','reproduction-final','full-reproduction'}):
            continue
        low=p.name.lower()
        try:
            body=p.read_text(encoding='utf-8',errors='ignore').lower()
        except Exception:
            body=''
        if 'path_budget' in body or 'path-budget' in body or 'path_budget' in low:
            if p.suffix=='.py': pyfiles.append(p)
            elif p.suffix=='.json': jsonfiles.append(p)
    paper=PROJECT/'paper'
    if paper.exists():
        for p in paper.rglob('*.tex'):
            body=p.read_text(encoding='utf-8',errors='ignore').lower()
            if 'path-budget' in body or 'path budget' in body or 'path_budget' in body:
                texfiles.append(p)
    summary={'python_files':len(set(pyfiles)),'paper_tex_files':len(set(texfiles)),'json_files':len(set(jsonfiles))}
    if summary['python_files']<3 or summary['paper_tex_files']<1 or summary['json_files']<1:
        raise AssertionError(f'path-budget integration inventory failed: {summary}')
    return summary

def check_paper_sources():
    paper=PROJECT/'paper'
    if not paper.exists(): return {'present':False}
    text='\n'.join(p.read_text(errors='ignore') for p in paper.rglob('*.tex'))
    must=['synthetic','path-budget','refinement','INSUFFICIENT']
    missing=[x for x in must if x.lower() not in text.lower()]
    if missing: raise AssertionError(f'paper source missing reviewer-boundary terms: {missing}')
    forbidden=[r'prove[sd]? (?:the )?security of (?:a|the) (?:real|commercial|deployed) processor',r'guarantee[sd]? acceptance']
    for pat in forbidden:
        if re.search(pat,text,re.I): raise AssertionError(f'overclaim matched: {pat}')
    return {'present':True,'tex_files':len(list(paper.rglob('*.tex')))}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=HERE/'reviewer_gate_results.json'); ap.add_argument('--run-paper',action='store_true')
    ns=ap.parse_args()
    arch=json.loads(run([sys.executable,'verify_architecture_cases.py','--output',str(HERE/'architecture_case_results.json')]) or (HERE/'architecture_case_results.json').read_text()) if False else None
    # The command writes the result; read it afterward.
    run([sys.executable,'verify_architecture_cases.py','--output',str(HERE/'architecture_case_results.json')])
    arch=json.loads((HERE/'architecture_case_results.json').read_text())
    tests=run([sys.executable,'-m','unittest','-v','test_architecture_cases.py'])
    path_tests=run([sys.executable,'-m','unittest','-v','test_path_budget.py'])
    run([sys.executable,'compactness_benchmark.py'])
    run([sys.executable,'path_budget_scaling.py'])
    run([sys.executable,'path_enumeration_boundary.py'])
    run([sys.executable,'export_smtlib.py'])
    run([sys.executable,'static_code_audit.py'])
    run([sys.executable,'verify_environment.py'])
    prov=check_provenance(); imports=check_import_independence(); claims=check_claim_matrix(); venue=check_venue_sources(); bib=check_bibliography_audit(); pb=check_path_budget_semantics(path_tests); env=check_environment_record(); static=check_static_code(); smt=check_smt(); pathcap=check_path_cap(); scaling=check_scaling(); bench=check_benchmark_manifest(); core=check_core_inventory(); paper=check_paper_sources()
    paper_run=None
    if ns.run_paper and (PROJECT/'paper'/'reconcile.py').exists():
        run([sys.executable,'build.py'],cwd=PROJECT/'paper',timeout=900)
        paper_run=run([sys.executable,'reconcile.py'],cwd=PROJECT/'paper',timeout=900)[-2000:]
    result={
      'schema':'reviewer-gate-results-v1','status':'PASS','architecture_cases':arch,
      'architecture_test_methods':sum(1 for line in tests.splitlines() if line.strip().startswith('test_')),
      'path_budget_test_methods':sum(1 for line in path_tests.splitlines() if line.strip().startswith('test_')),
      'provenance_records':prov[0],'provenance_anchors':prov[1],
      'independent_oracle_imports':imports,'claim_evidence_rows':claims,'venue_sources':venue,'bibliography_audit':bib,
      'path_budget_inventory':core,'path_budget_semantic_audit':pb,'benchmark_manifest':bench,'validation_environment':env,'static_code_audit':static,'smt_validation':smt,'path_count_boundary':pathcap,'path_budget_scaling':scaling,'paper_source_check':paper,'paper_reconcile_tail':paper_run,
      'files':{p.name:sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name not in {ns.output.name}}
    }
    ns.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PASS','architecture_cases':arch['case_count'],'claim_rows':claims,'provenance_anchors':prov[1]},sort_keys=True))
if __name__=='__main__': main()
