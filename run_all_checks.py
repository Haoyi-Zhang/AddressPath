#!/usr/bin/env python3
"""Single entry point for the original reproduction plus reviewer-hardening gates."""
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def run(cmd,cwd=HERE,timeout=1800):
    p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    if p.returncode: raise SystemExit(f"FAILED: {' '.join(map(str,cmd))}\n{p.stdout}")
    return p.stdout

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=HERE/'full-reproduction'); ap.add_argument('--skip-core',action='store_true')
    ns=ap.parse_args(); ns.output.mkdir(parents=True,exist_ok=True)
    stages=[]
    if not ns.skip_core:
        for stage in ('core','tpeg-middle','tpeg-tail','validation'):
            stages.append({'stage':stage,'tail':run([sys.executable,'reproduce.py','--output',str(ns.output),'--stage',stage])[-1000:]})
    gate=HERE/'reviewer_hardening'/'reviewer_gate.py'
    run([sys.executable,str(gate),'--output',str(ns.output/'reviewer_gate_results.json')],cwd=gate.parent)
    g=json.loads((ns.output/'reviewer_gate_results.json').read_text())
    out={'schema':'full-project-reproduction-v1','status':'PASS','core_stages':[x['stage'] for x in stages],'reviewer_gate':g['status']}
    (ns.output/'run_all_summary.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__': main()
