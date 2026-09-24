#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, json, random, statistics, sys, time
from pathlib import Path
from fractions import Fraction

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import path_budget as pb
import independent_path_budget as ipb

SCHEMA_VERSION="reviewer-hardening-v1"
DEV_SEEDS=tuple(range(1000,1200))
HOLDOUT_SEEDS=tuple(range(9000,9500))

def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def random_case(seed:int):
    r=random.Random(seed)
    groups=r.randint(1,4)
    variables=[]; bounds={}; constraints=[]; edges=[]; nodes=[]
    edge_index=0; total_cap=0
    nodes=["n0"]
    for g in range(groups):
        width=r.randint(1,3); cap=r.randint(0,width)
        total_cap+=cap
        coeffs={}
        for j in range(width):
            v=f"v{g}_{j}"; variables.append(v); bounds[v]=[0,1]; coeffs[v]=1
            edges.append({"name":f"e{edge_index}","src":f"n{edge_index}","dst":f"n{edge_index+1}","open":{"coeffs":{v:1},"const":0}})
            edge_index+=1; nodes.append(f"n{edge_index}")
        constraints.append({"name":f"g{g}","coeffs":coeffs,"rhs":cap})
    safe=total_cap <= len(edges)-1
    # Roughly one third are unsafe by relaxing a random group to full width.
    if seed%3==0:
        for c in constraints:
            c["rhs"]=len(c["coeffs"])
        safe=False
    model={"name":f"rand_{seed}","variables":variables,"bounds":bounds,"nodes":nodes,"source":nodes[0],"bad":nodes[-1],"constraints":constraints,"edges":edges}
    cert={"type":"path_budget","model":model["name"],"obligations":[{"path":[e["name"] for e in edges],"multipliers":{c["name"]:1 for c in constraints}}]}
    return model,cert,safe

def rename_case(model,cert):
    m=copy.deepcopy(model); c=copy.deepcopy(cert)
    vmap={v:f"rv_{i}" for i,v in enumerate(reversed(m["variables"]))}
    nmap={n:f"rn_{i}" for i,n in enumerate(reversed(m["nodes"]))}
    emap={e["name"]:f"re_{i}" for i,e in enumerate(reversed(m["edges"]))}
    cmap={x["name"]:f"rc_{i}" for i,x in enumerate(reversed(m["constraints"]))}
    m["variables"]=[vmap[v] for v in m["variables"]]
    m["bounds"]={vmap[v]:b for v,b in m["bounds"].items()}
    m["nodes"]=[nmap[n] for n in m["nodes"]]; m["source"]=nmap[m["source"]]; m["bad"]=nmap[m["bad"]]
    for x in m["constraints"]:
        x["name"]=cmap[x["name"]]; x["coeffs"]={vmap[v]:a for v,a in x["coeffs"].items()}
    for e in m["edges"]:
        e["name"]=emap[e["name"]]; e["src"]=nmap[e["src"]]; e["dst"]=nmap[e["dst"]]
        e["open"]["coeffs"]={vmap[v]:a for v,a in e["open"]["coeffs"].items()}
    m["name"] += "_renamed"; c["model"]=m["name"]
    for ob in c["obligations"]:
        ob["path"]=[emap[e] for e in ob["path"]]; ob["multipliers"]={cmap[k]:v for k,v in ob["multipliers"].items()}
    return m,c

def scale_constraints(model,cert,factor=3):
    m=copy.deepcopy(model); c=copy.deepcopy(cert); m["name"] += "_scaled"; c["model"]=m["name"]
    for con in m["constraints"]:
        con["coeffs"]={v:a*factor for v,a in con["coeffs"].items()}; con["rhs"]*=factor
    for ob in c["obligations"]:
        ob["multipliers"]={k:{"num":1,"den":factor} for k in ob["multipliers"]}
    return m,c

def diamond(depth:int):
    nodes=["s"]; edges=[]; cur="s"
    for i in range(depth):
        a=f"a{i}"; b=f"b{i}"; j=f"j{i}"; nodes += [a,b,j]
        edges += [
            {"name":f"u{i}","src":cur,"dst":a,"open":{"coeffs":{},"const":0}},
            {"name":f"d{i}","src":cur,"dst":b,"open":{"coeffs":{},"const":0}},
            {"name":f"uj{i}","src":a,"dst":j,"open":{"coeffs":{},"const":0}},
            {"name":f"dj{i}","src":b,"dst":j,"open":{"coeffs":{},"const":0}},
        ]; cur=j
    return {"name":f"diamond_{depth}","variables":["dummy"],"bounds":{"dummy":[0,0]},"nodes":nodes,"source":"s","bad":cur,"constraints":[],"edges":edges}

def run_suite(output:Path):
    start=time.perf_counter(); output.mkdir(parents=True,exist_ok=True)
    results={"schema":SCHEMA_VERSION,"dev":{},"holdout":{},"metamorphic":{},"separation":{},"limits":{},"mutations":{}}
    for label,seeds in (("dev",DEV_SEEDS),("holdout",HOLDOUT_SEEDS)):
        correct=0; safe_count=0; proved=0; unsafe_rejected=0; uniform_zero=0; cert_bytes=[]
        for seed in seeds:
            raw,cert,expected_safe=random_case(seed); model=pb.parse_model(raw)
            a=pb.oracle(model); b=ipb.oracle(raw)
            if a["safe"]!=b["safe"] or a["safe"]!=expected_safe: raise AssertionError((seed,a,b,expected_safe))
            if expected_safe:
                safe_count+=1
                pb.check_certificate(model,cert); ipb.check(raw,cert); proved+=1
                cert_bytes.append(len(json.dumps(cert,sort_keys=True,separators=(",",":"))))
                states=list(pb.allowed_states(model))
                if any(all(pb.eval_affine(e.open_expr,s)==0 for s in states) for e in model.edges): uniform_zero+=1
            else:
                try: pb.check_certificate(model,cert)
                except Exception: unsafe_rejected+=1
                else: raise AssertionError("unsafe certificate accepted")
            correct+=1
        results[label]={"cases":correct,"safe":safe_count,"proved":proved,"unsafe_rejected":unsafe_rejected,"uniform_zero_proved":uniform_zero,"path_budget_proved":proved,"mean_certificate_bytes":(sum(cert_bytes)/len(cert_bytes) if cert_bytes else 0),"seed_sha256":hashlib.sha256(','.join(map(str,seeds)).encode()).hexdigest()}
    # Metamorphic invariance on a representative safe case.
    raw,cert,_=random_case(1001)
    base=pb.check_certificate(pb.parse_model(raw),cert)
    for name,transform in (("renaming",rename_case),("positive_constraint_scaling",scale_constraints)):
        rm,rc=transform(raw,cert); got=pb.check_certificate(pb.parse_model(rm),rc); ipb.check(rm,rc)
        results["metamorphic"][name]={"status":"PASS","paths":got["paths"]}
    # Exponential representation separation and exact oracle for n<=8.
    sep=[]
    for n in range(1,17):
        raw,cert=pb.make_alternating_model(n); model=pb.parse_model(raw)
        pb.check_certificate(model,cert); ipb.check(raw,cert)
        row={"n":n,"variables":2*n,"allowed_formula":3**n,"max_signatures_formula":2**n,"certificate_obligations":1,"certificate_multipliers":n}
        if n<=8:
            o=pb.oracle(model,state_cap=3**n+1); ms=pb.max_signatures(model,state_cap=3**n+1)
            if o["allowed_states"]!=3**n or len(ms)!=2**n or not o["safe"]: raise AssertionError("separation oracle mismatch")
            row.update({"oracle_allowed":o["allowed_states"],"oracle_max_signatures":len(ms)})
        sep.append(row)
    results["separation"]={"rows":sep,"largest_checked_n":4096}
    # Large non-enumerative certificate check.
    raw,cert=pb.make_alternating_model(4096,"alternating_4096")
    t=time.perf_counter(); got=pb.check_certificate(pb.parse_model(raw),cert); ipb.check(raw,cert)
    results["separation"]["n4096_check_seconds"]=time.perf_counter()-t
    results["separation"]["n4096_paths"]=got["paths"]
    # Integer-only safe case is deliberately outside rational path-budget completeness.
    iom=pb.make_integer_only_model(); io=pb.oracle(pb.parse_model(iom))
    fake={"type":"path_budget","model":iom["name"],"obligations":[{"path":["e"],"multipliers":{"half":{"num":1,"den":2}}}]}
    rejected=False
    try: pb.check_certificate(pb.parse_model(iom),fake)
    except Exception: rejected=True
    if not io["safe"] or not rejected: raise AssertionError("incompleteness witness failed")
    results["separation"]["integer_only_incompleteness"]={"oracle_safe":io["safe"],"path_budget_rejected":rejected}
    # Path explosion is fail-closed at the documented cap.
    p12=len(pb.canonical_paths(pb.parse_model(diamond(12)),4096))
    limit_rejected=False
    try: pb.canonical_paths(pb.parse_model(diamond(13)),4096)
    except pb.PathLimitExceeded: limit_rejected=True
    if p12!=4096 or not limit_rejected: raise AssertionError("path cap test failed")
    results["limits"]={"cap":4096,"diamond12_paths":p12,"diamond13_rejected":limit_rejected}
    # Mutation tests.
    raw,cert=pb.make_alternating_model(4,"mutation_base"); model=pb.parse_model(raw)
    mutations=[]
    def reject(label,c):
        ok=False
        try: pb.check_certificate(model,c)
        except Exception: ok=True
        if not ok: raise AssertionError(f"mutation accepted: {label}")
        mutations.append(label)
    c=copy.deepcopy(cert); c["obligations"]=[]; reject("missing_path",c)
    c=copy.deepcopy(cert); c["obligations"]*=2; reject("duplicate_path",c)
    c=copy.deepcopy(cert); c["obligations"][0]["multipliers"].pop("pair_0"); reject("missing_multiplier",c)
    c=copy.deepcopy(cert); c["obligations"][0]["multipliers"]["pair_0"]=-1; reject("negative_multiplier",c)
    c=copy.deepcopy(cert); c["obligations"][0]["multipliers"]["unknown"]=1; reject("unknown_constraint",c)
    c=copy.deepcopy(cert); c["model"]="other"; reject("cross_model",c)
    results["mutations"]={"rejected":len(mutations),"names":mutations}
    results["elapsed_seconds"]=time.perf_counter()-start
    results["status"]="PASS"
    dump(output/"reviewer_hardening_results.json",results)
    rows=["split,cases,safe,proved,unsafe_rejected,uniform_zero_proved,path_budget_proved,mean_certificate_bytes"]
    for s in ("dev","holdout"):
        r=results[s]; rows.append(f"{s},{r['cases']},{r['safe']},{r['proved']},{r['unsafe_rejected']},{r['uniform_zero_proved']},{r['path_budget_proved']},{r['mean_certificate_bytes']:.2f}")
    (output/"holdout_summary.csv").write_text("\n".join(rows)+"\n")
    return results

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,default=HERE/"results")
    args=ap.parse_args(); result=run_suite(args.output); print(json.dumps({"status":result["status"],"output":str(args.output)},sort_keys=True))
if __name__=="__main__": main()
