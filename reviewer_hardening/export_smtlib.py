#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def q(name:str)->str:
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name): raise ValueError(name)
    return name

def expr(coeffs):
    terms=[]
    for x,a in sorted(coeffs.items()):
        if a==0: continue
        terms.append(q(x) if a==1 else f'(- {q(x)})' if a==-1 else f'(* {a} {q(x)})')
    return '0' if not terms else terms[0] if len(terms)==1 else f"(+ {' '.join(terms)})"

def paths(c):
    out={n:[] for n in c['nodes']}
    for e in c['edges']: out[e['src']].append(e)
    for n in out: out[n].sort(key=lambda e:e['id'])
    ans=[]
    def dfs(n,seen,es):
        if n in c['bad_nodes']: ans.append(list(es)); return
        for e in out[n]:
            if e['dst'] in seen: raise ValueError('cycle')
            dfs(e['dst'],seen|{e['dst']},es+[e])
    dfs(c['source_node'],{c['source_node']},[]); return ans

def render(c):
    lines=['(set-logic QF_LIA)']
    for x,(lo,hi) in sorted(c['variables'].items()):
        lines += [f'(declare-const {q(x)} Int)',f'(assert (<= {lo} {q(x)}))',f'(assert (<= {q(x)} {hi}))']
    for z in c['constraints']:
        op={'<=':'<=','>=':'>=','=':'='}[z['op']]
        lines.append(f"(assert ({op} {expr(z['coefficients'])} {z['rhs']}))")
    disj=[]
    for p in paths(c):
        atoms=[f"(= {q(e['open_var'])} 1)" for e in p]
        disj.append(atoms[0] if len(atoms)==1 else f"(and {' '.join(atoms)})")
    bad='false' if not disj else disj[0] if len(disj)==1 else f"(or {' '.join(disj)})"
    lines += [f'(assert {bad})','(check-sat)','(get-model)']
    return '\n'.join(lines)+'\n'

def main():
    data=json.loads((HERE/'architecture_cases.json').read_text())
    out=HERE/'smtlib_cases'; out.mkdir(exist_ok=True)
    expected={}
    for c in data['cases']:
        (out/f"{c['id']}.smt2").write_text(render(c))
        expected[c['id']]='unsat' if c['expected']['ground_truth']=='PROVED' else 'sat' if c['expected']['ground_truth']=='INSUFFICIENT' else 'unknown'
    (out/'expected.json').write_text(json.dumps(expected,indent=2,sort_keys=True)+'\n')
    z3=shutil.which('z3')
    results={}
    if z3:
        version=subprocess.check_output([z3,'-version'],text=True).strip()
        for cid,want in expected.items():
            r=subprocess.run([z3,'-smt2',str(out/f'{cid}.smt2')],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            first=(r.stdout.strip().splitlines() or [''])[0]
            if first!=want: raise AssertionError(f'{cid}: z3={first}, expected={want}, stderr={r.stderr}')
            results[cid]=first
        status='PASS'; engine=version
    else:
        status='NOT_RUN'; engine='z3 executable unavailable; SMT-LIB files remain independently checkable'
    (HERE/'smtlib_live_results.json').write_text(json.dumps({'schema':'architecture-smtlib-results-v1','status':status,'engine':engine,'results':results},indent=2,sort_keys=True)+'\n')
if __name__=='__main__': main()
