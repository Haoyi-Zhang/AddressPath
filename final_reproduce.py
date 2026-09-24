#!/usr/bin/env python3
"""Single clean-entry reproduction driver.

The driver never asks the legacy runner to write into a directory that this
wrapper has already created.  This closes the prior output-directory failure.
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def run(cmd, cwd, log):
    start=time.perf_counter()
    p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    log.parent.mkdir(parents=True,exist_ok=True)
    log.write_text(p.stdout,encoding="utf-8")
    if p.returncode:
        raise SystemExit(f"command failed ({p.returncode}); see {log}: {' '.join(map(str,cmd))}")
    return time.perf_counter()-start

def main():
    ap=argparse.ArgumentParser(description="Reproduce the complete artifact from a clean output directory")
    ap.add_argument("--output",type=Path,default=ROOT/"reproduction-final")
    ap.add_argument("--keep",action="store_true",help="refuse to delete an existing output directory")
    args=ap.parse_args()
    out=args.output.resolve()
    if out.exists():
        if args.keep: raise SystemExit(f"output exists: {out}")
        shutil.rmtree(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    legacy=ROOT/"reproduce.py"
    if not legacy.exists(): raise SystemExit("missing legacy reproduce.py")
    help_text=subprocess.run([sys.executable,str(legacy),"--help"],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout
    timings={}; commands=[]
    if "--stage" in help_text:
        stages=("core","tpeg-middle","tpeg-tail","validation")
        for i,stage in enumerate(stages):
            cmd=[sys.executable,str(legacy),"--output",str(out),"--stage",stage]
            timings[stage]=run(cmd,ROOT,out.parent/f"{out.name}.{stage}.log")
            commands.append(cmd)
    else:
        cmd=[sys.executable,str(legacy),"--output",str(out)]
        timings["legacy"]=run(cmd,ROOT,out.parent/f"{out.name}.legacy.log")
        commands.append(cmd)
    hard=ROOT/"reviewer_hardening"/"run_suite.py"
    cmd=[sys.executable,str(hard),"--output",str(out/"reviewer_hardening")]
    timings["reviewer_hardening"]=run(cmd,ROOT,out.parent/f"{out.name}.reviewer_hardening.log")
    commands.append(cmd)
    arch=ROOT/"reviewer_hardening"/"architecture_cases.py"
    cmd=[sys.executable,str(arch),"--output",str(out/"architecture_cases")]
    timings["architecture_cases"]=run(cmd,ROOT,out.parent/f"{out.name}.architecture_cases.log")
    commands.append(cmd)
    summary={"status":"PASS","root":str(ROOT),"output":str(out),"timings_seconds":timings,
             "commands":[[str(x) for x in c] for c in commands],"python":sys.version}
    (out/"final_reproduction_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":"PASS","output":str(out)},sort_keys=True))
if __name__=="__main__": main()
