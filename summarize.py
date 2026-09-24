"""Reconcile every table entry against case-level exact results."""
from pathlib import Path
from collections import Counter
from fractions import Fraction
import argparse,csv,json

def summarize(source,dest):
    results=[json.loads(p.read_text()) for p in sorted(source.glob('case-*.json'))]
    if len(results)!=86 or len({r['id'] for r in results})!=86:raise ValueError('expected the fixed 86-case corpus')
    if any(r['exact_status']!=r['oracle_status'] for r in results):raise ValueError('oracle mismatch')
    for r in results:
        if r['certificate_kind'] is None:
            if r['exact_status']!='INSUFFICIENT':raise ValueError('missing certificate')
        elif r['checker_result']!=r['exact_status']:raise ValueError('checker mismatch')
    dest.mkdir(parents=True,exist_ok=True)
    keys=['family','cases','exact_proved','exact_insufficient','exact_inconsistent','linear_proved','quantized_proved']
    families=[]
    for fam in sorted({r['family'] for r in results}):
        rr=[r for r in results if r['family']==fam]
        families.append(dict(zip(keys,[fam,len(rr),*[sum(r['exact_status']==s for r in rr) for s in ['PROVED','INSUFFICIENT','INCONSISTENT']],sum(r['linear_status']=='PROVED' for r in rr),sum(r['quantized_status']=='PROVED' for r in rr)])))
    with (dest/'families.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(families)
    lines=[]
    for r in families:
        lines.append(r['family'].replace('_',r'\_')+' & '+' & '.join(str(r[k]) for k in keys[1:])+r' \\')
    (dest/'families.tex').write_text('\n'.join(lines)+'\n')
    resources=[json.loads(p.read_text()) for p in sorted(source.glob('resources-*.json'))]
    certsizes=[p.stat().st_size for p in sorted((source/'certificates').glob('case-*.json'))]
    summary={'cases':len(results),'exact':dict(Counter(r['exact_status'] for r in results)),
             'linear':dict(Counter(r['linear_status'] for r in results)),
             'quantized':dict(Counter(r['quantized_status'] for r in results)),
             'certificates':dict(Counter(r['certificate_kind'] or 'none' for r in results)),
             'grid_states_per_enumerator':sum(r['enumerated_states'] for r in results),
             'basis_systems':sum(r['basis_systems'] for r in results),
             'cpu_s':sum(r['cpu_s'] for r in resources),'wall_s':sum(r['wall_s'] for r in resources),
             'peak_rss_kib':max(r['peak_rss_kib'] for r in resources),
             'certificate_bytes':{'sum':sum(certsizes),'min':min(certsizes),'max':max(certsizes)},
             'maxima':{k:max(r[k] for r in results) for k in ['inputs','nodes','observables','inequalities','max_compiled_bits','enumerated_states']},
             'finite_cover_state_visits':sum(r['enumerated_states'] for r in results if r['certificate_kind']=='finite_cover')}
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    # Plot data: N=2 accounting, five fixed widths; values are exact run results.
    with (dest/'accounting.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['width','rational_upper','finite_upper'])
        for i,width in zip(range(6,11),['0','1/4','3/4','1','5/4']):
            r=next(r for r in results if r['id']==f'case-{i:03}')
            w.writerow([float(Fraction(width)),float(Fraction(r['relaxed_upper'])),float(Fraction(r['oracle_max_q']))])
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',default='results');p.add_argument('--output',default='tables')
    a=p.parse_args();root=Path(__file__).resolve().parent
    print(json.dumps(summarize(root/a.source,root/a.output),indent=2))
