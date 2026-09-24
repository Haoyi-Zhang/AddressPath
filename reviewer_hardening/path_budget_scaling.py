#!/usr/bin/env python3
"""Structural and descriptive timing scaling for a non-enumerative path budget."""
from __future__ import annotations
import csv,json,platform,statistics,time,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def certificate(n:int):
    return {'schema':'alternating-pair-path-budget-v1','pairs':n,
            'target_coefficients':{f'x{i}':1 for i in range(n)}|{f'y{i}':1 for i in range(n)},
            'rows':[{'id':f'pair_{i}','coefficients':{f'x{i}':1,f'y{i}':1},'rhs':1,'multiplier':1} for i in range(n)],
            'required_rhs':2*n-1}

def verify(c):
    n=c['pairs']; target=c['target_coefficients']; acc={k:0 for k in target}; rhs=0
    seen=set()
    for row in c['rows']:
        if row['id'] in seen: raise ValueError('duplicate row')
        seen.add(row['id']); m=row['multiplier']
        if not isinstance(m,int) or isinstance(m,bool) or m<0: raise ValueError('bad multiplier')
        for x,a in row['coefficients'].items():
            if x not in acc: raise ValueError('unknown coefficient')
            acc[x]+=m*a
        rhs+=m*row['rhs']
    if acc!=target: raise ValueError('coefficient mismatch')
    if rhs>c['required_rhs']: raise ValueError('insufficient bound')
    return rhs

def main():
    rows=[]
    for n in [1,2,4,8,16,32,64,128,256,512,1024,2048,4096]:
        c=certificate(n); verify(c)
        payload=(json.dumps(c,sort_keys=True,separators=(',',':'))+'\n').encode()
        for _ in range(5): verify(c)
        samples=[]
        reps=101 if n<=256 else 31
        for _ in range(reps):
            t=time.process_time_ns(); verify(c); samples.append(time.process_time_ns()-t)
        samples.sort(); p95=samples[min(len(samples)-1,int(0.95*(len(samples)-1)))]
        rows.append({'pairs':n,'binary_variables':2*n,'explicit_bad_paths':1,
                     'allowed_states_symbolic':f'3^{n}','maximal_signatures_symbolic':f'2^{n}',
                     'witness_rows':n,'certificate_bytes':len(payload),
                     'median_check_cpu_us':round(statistics.median(samples)/1000,3),
                     'p95_check_cpu_us':round(p95/1000,3),'repetitions':reps})
    with (HERE/'path_budget_scaling.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    meta={'schema':'path-budget-scaling-v1','status':'PASS','timing_interpretation':'descriptive single-process CPU measurements; structural columns are the portable result','python':sys.version,'platform':platform.platform(),'rows':len(rows)}
    (HERE/'path_budget_scaling_environment.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n')
if __name__=='__main__': main()
