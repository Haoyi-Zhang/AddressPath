#!/usr/bin/env python3
"""Topology-shaped, synthetic-evidence cases.

Names indicate the control-flow motif being modeled; they are not extracted
RTL models and do not establish the safety of any named implementation.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import path_budget as pb
import independent_path_budget as ipb

def chain(name,variables,rhs):
    nodes=[f"n{i}" for i in range(len(variables)+1)]
    model={"name":name,"variables":variables,"bounds":{v:[0,1] for v in variables},"nodes":nodes,"source":nodes[0],"bad":nodes[-1],
           "constraints":[{"name":"joint_gate","coeffs":{v:1 for v in variables},"rhs":rhs}],
           "edges":[{"name":f"e{i}","src":nodes[i],"dst":nodes[i+1],"open":{"coeffs":{v:1},"const":0}} for i,v in enumerate(variables)]}
    cert={"type":"path_budget","model":name,"obligations":[{"path":[f"e{i}" for i in range(len(variables))],"multipliers":{"joint_gate":1}}]}
    return model,cert

def cases():
    out=[]
    out.append(("sv39_permission_chain",)+chain("sv39_permission_chain",["walk_valid","leaf_permission","access_match"],2)+("safe",))
    out.append(("two_stage_translation",)+chain("two_stage_translation",["vs_accept","g_accept"],1)+("safe",))
    m={"name":"iommu_context_fanout","variables":["ctx","proc","device","page"],"bounds":{v:[0,1] for v in ["ctx","proc","device","page"]},
       "nodes":["s","a","b","bad"],"source":"s","bad":"bad",
       "constraints":[{"name":"left_joint","coeffs":{"ctx":1,"proc":1},"rhs":1},{"name":"right_joint","coeffs":{"device":1,"page":1},"rhs":1}],
       "edges":[{"name":"ctx","src":"s","dst":"a","open":{"coeffs":{"ctx":1},"const":0}},
                {"name":"proc","src":"a","dst":"bad","open":{"coeffs":{"proc":1},"const":0}},
                {"name":"device","src":"s","dst":"b","open":{"coeffs":{"device":1},"const":0}},
                {"name":"page","src":"b","dst":"bad","open":{"coeffs":{"page":1},"const":0}}]}
    c={"type":"path_budget","model":m["name"],"obligations":[
       {"path":["ctx","proc"],"multipliers":{"left_joint":1}},
       {"path":["device","page"],"multipliers":{"right_joint":1}}]}
    out.append((m["name"],m,c,"safe"))
    out.append(("ptw_recheck_chain",)+chain("ptw_recheck_chain",["cache_hit","pte_valid","permission_ok","epoch_match"],3)+("safe",))
    m=pb.make_integer_only_model("integer_rounding_fallback")
    out.append((m["name"],m,None,"safe_exact_only"))
    m={"name":"unconstrained_bypass","variables":["gate"],"bounds":{"gate":[1,1]},"nodes":["s","bad"],"source":"s","bad":"bad","constraints":[],
       "edges":[{"name":"bypass","src":"s","dst":"bad","open":{"coeffs":{"gate":1},"const":0}}]}
    out.append((m["name"],m,None,"unsafe"))
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,default=HERE/"architecture-results"); args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True); rows=[]
    for name,raw,cert,expected in cases():
        model=pb.parse_model(raw); prod=pb.oracle(model); indep=ipb.oracle(raw)
        if prod["safe"]!=indep["safe"]: raise AssertionError(name)
        cert_status="not_applicable"
        if cert is not None:
            pb.check_certificate(model,cert); ipb.check(raw,cert); cert_status="accepted"
        if expected=="safe" and not prod["safe"]: raise AssertionError(name)
        if expected=="unsafe" and prod["safe"]: raise AssertionError(name)
        if expected=="safe_exact_only":
            if not prod["safe"]: raise AssertionError(name)
        (args.output/f"{name}.model.json").write_text(json.dumps(raw,indent=2,sort_keys=True)+"\n")
        if cert is not None: (args.output/f"{name}.certificate.json").write_text(json.dumps(cert,indent=2,sort_keys=True)+"\n")
        rows.append({"name":name,"scope":"synthetic evidence over an architecture-shaped topology","expected":expected,"oracle_safe":prod["safe"],"allowed_states":prod["allowed_states"],"path_budget":cert_status})
    result={"status":"PASS","cases":rows,"scope_warning":"These cases do not model or certify any concrete processor or RTL implementation."}
    (args.output/"summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":"PASS","cases":len(rows)}))
if __name__=="__main__": main()
