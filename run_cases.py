"""Run a bounded, one-worker group. Results contain no violating state."""
from pathlib import Path
import argparse,json,os,resource,sys,time
sys.path.insert(0,str(Path(__file__).parent/'src'))
import checker,producer,oracle

def run(ids,output,root):
    allowed=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{allowed[0]})
    resource.setrlimit(resource.RLIMIT_CPU,(110,115))
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    output.mkdir(parents=True,exist_ok=True);(output/'certificates').mkdir(exist_ok=True)
    start=time.monotonic();cpu_start=time.process_time();results=[]
    for name in ids:
        if time.monotonic()-start>100: raise RuntimeError('chunk wall budget exceeded')
        model=checker.load(root/'cases'/(name+'.json'))
        t=time.process_time();begin=time.monotonic()
        result=producer.make(model)
        proposed_cpu=time.process_time()-t
        t=time.process_time();ref=oracle.evaluate(model);oracle_cpu=time.process_time()-t
        if ref['status']!=result['exact_status'] or ref['feasible_states']!=result['feasible_finite_states']:
            raise AssertionError('direct-DAG finite oracle disagreement')
        cert=result.pop('certificate');t=time.process_time()
        if cert is not None:
            checked=checker.verify(model,cert)
            if checked!=result['exact_status']: raise AssertionError('checker disagreement')
            (output/'certificates'/(name+'.json')).write_text(json.dumps(cert,indent=2)+'\n')
        else: checked='NO_CERTIFICATE'
        checker_cpu=time.process_time()-t
        bounds,A,b,c,q0=checker.compile_model(model)
        result.update({'id':name,'family':model['family'],'oracle_status':ref['status'],
                       'oracle_max_q':ref['max_q'],'enumerated_states':ref['states'],
                       'checker_result':checked,'certificate_kind':None if cert is None else cert['kind'],
                       'producer_cpu_s':proposed_cpu,'oracle_cpu_s':oracle_cpu,'checker_cpu_s':checker_cpu,
                       'wall_s':time.monotonic()-begin,'inputs':len(bounds),'nodes':len(model['nodes']),
                       'observables':len(model['observations']),'inequalities':len(A),
                       'max_compiled_bits':max(max(v.numerator.bit_length(),v.denominator.bit_length()) for v in [*b,*c,q0,*(x for row in A for x in row)]),
                       'naive_consistency_false_proof':ref['status']=='INSUFFICIENT'})
        (output/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n');results.append(result)
    usage={'cases':ids,'workers':1,'cpu_s':time.process_time()-cpu_start,'wall_s':time.monotonic()-start,
           'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'basis_systems':sum(r['basis_systems'] for r in results),
           'finite_states_per_enumerator':sum(r['enumerated_states'] for r in results),
           'certificates_checked':sum(r['certificate_kind'] is not None for r in results)}
    (output/('resources-'+ids[0]+'-'+ids[-1]+'.json')).write_text(json.dumps(usage,indent=2)+'\n')
    print(json.dumps(usage))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--ids',nargs='+');ap.add_argument('--start',type=int,default=1);ap.add_argument('--end',type=int,default=16);ap.add_argument('--output',default='results')
    a=ap.parse_args();root=Path(__file__).resolve().parent
    ids=a.ids or [f'case-{i:03}' for i in range(a.start,a.end+1)]
    run(ids,root/a.output,root)
