#!/usr/bin/env python3
"""Closed-form and finite checks for the alternating-pair compactness family."""
from __future__ import annotations
import csv,itertools,json
from pathlib import Path
HERE=Path(__file__).resolve().parent

def signature(bits):
    return tuple(i for i,b in enumerate(bits) if b)

def exact_small(n:int):
    allowed=[]
    for bits in itertools.product((0,1),repeat=2*n):
        if all(bits[2*i]+bits[2*i+1] <= 1 for i in range(n)):
            allowed.append(signature(bits))
    maximal=[]
    sets=[set(s) for s in allowed]
    for i,s in enumerate(sets):
        if not any(s<t for j,t in enumerate(sets) if i!=j): maximal.append(tuple(sorted(s)))
    return len(allowed),len(set(maximal))

def cert(n:int):
    return {'method':'path_budget','path':[f'e{i}{side}' for i in range(n) for side in ('a','b')],
            'multipliers':{f'pair_{i}':'1' for i in range(n)},'proved_upper_bound':n}

def main():
    rows=[]
    for n in range(1,17):
        a=3**n; m=2**n
        if n<=8:
            ea,em=exact_small(n)
            if (ea,em)!=(a,m): raise AssertionError((n,ea,em,a,m))
        c=cert(n); b=len((json.dumps(c,sort_keys=True,separators=(',',':'))+'\n').encode())
        rows.append({'pairs':n,'binary_variables':2*n,'allowed_states':a,'maximal_signatures':m,'canonical_bad_paths':1,'path_budget_witness_rows':n,'path_budget_certificate_bytes':b})
    with (HERE/'compactness_benchmark.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (HERE/'compactness_benchmark_summary.json').write_text(json.dumps({'schema':'compactness-benchmark-v1','status':'PASS','closed_form':'allowed_states=3^n; maximal_signatures=2^n; path-budget witness rows=n','finite_validation_through_n':8,'rows':len(rows)},indent=2,sort_keys=True)+'\n')
if __name__=='__main__': main()
