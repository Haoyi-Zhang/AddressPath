#!/usr/bin/env python3
"""Independent exact checker for the specification-derived topology cases.

This file intentionally imports only the Python standard library and does not
import the production TPEG generator or checker.  It provides a second parser,
state enumerator, path enumerator, and compact path-budget check for the four
small case-study models.
"""
from __future__ import annotations
import argparse, itertools, json, sys, re
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

ALLOWED_TOP = {"schema", "scope", "cases"}
ALLOWED_CASE = {"id","source","variables","constraints","nodes","source_node","bad_nodes","edges","expected","claim_boundary","certificate"}
ALLOWED_CONSTRAINT = {"id","coefficients","op","rhs"}
ALLOWED_EDGE = {"id","src","dst","open_var"}

def load_strict(path: Path) -> Any:
    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"duplicate JSON key: {k}")
            out[k] = v
        return out
    with path.open("r", encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=hook, parse_float=lambda s: (_ for _ in ()).throw(ValueError("floats forbidden")))

def require_keys(obj: Mapping[str, Any], allowed: set[str], where: str) -> None:
    extra = set(obj) - allowed
    if extra:
        raise ValueError(f"{where}: unknown keys {sorted(extra)}")

def validate_case(c: Mapping[str, Any]) -> None:
    require_keys(c, ALLOWED_CASE, c.get("id", "case"))
    for key in ALLOWED_CASE:
        if key not in c:
            raise ValueError(f"{c.get('id','case')}: missing {key}")
    if not isinstance(c["id"], str) or not c["id"]:
        raise ValueError("case id must be nonempty")
    nodes = c["nodes"]
    if not isinstance(nodes, list) or len(nodes) != len(set(nodes)) or not all(isinstance(n,str) and n for n in nodes):
        raise ValueError(f"{c['id']}: invalid nodes")
    if c["source_node"] not in nodes or any(b not in nodes for b in c["bad_nodes"]):
        raise ValueError(f"{c['id']}: source/bad node missing")
    variables = c["variables"]
    if not isinstance(variables, dict) or not variables:
        raise ValueError(f"{c['id']}: variables must be nonempty object")
    for name, bounds in variables.items():
        if not isinstance(name,str) or not isinstance(bounds,list) or len(bounds)!=2 or not all(isinstance(x,int) and not isinstance(x,bool) for x in bounds):
            raise ValueError(f"{c['id']}: invalid bounds for {name}")
        if bounds[0] > bounds[1] or bounds[1]-bounds[0] > 16:
            raise ValueError(f"{c['id']}: invalid/excessive domain for {name}")
    edge_ids=set()
    for e in c["edges"]:
        require_keys(e, ALLOWED_EDGE, f"{c['id']} edge")
        if set(e) != ALLOWED_EDGE:
            raise ValueError(f"{c['id']}: incomplete edge")
        if e["id"] in edge_ids: raise ValueError(f"{c['id']}: duplicate edge id")
        edge_ids.add(e["id"])
        if e["src"] not in nodes or e["dst"] not in nodes or e["open_var"] not in variables:
            raise ValueError(f"{c['id']}: malformed edge {e['id']}")
        lo,hi=variables[e["open_var"]]
        if lo < 0 or hi > 1:
            raise ValueError(f"{c['id']}: edge variables must be binary")
    for q in c["constraints"]:
        require_keys(q, ALLOWED_CONSTRAINT, f"{c['id']} constraint")
        if set(q) != ALLOWED_CONSTRAINT or q["op"] not in {"<=","=",">="} or not isinstance(q["rhs"],int):
            raise ValueError(f"{c['id']}: invalid constraint")
        if not isinstance(q["coefficients"],dict): raise ValueError("coefficients must be object")
        for name,coef in q["coefficients"].items():
            if name not in variables or not isinstance(coef,int) or isinstance(coef,bool):
                raise ValueError(f"{c['id']}: invalid coefficient")

def sat_constraint(q: Mapping[str,Any], state: Mapping[str,int]) -> bool:
    lhs=sum(int(a)*state[x] for x,a in q["coefficients"].items())
    return lhs <= q["rhs"] if q["op"]=="<=" else lhs >= q["rhs"] if q["op"]==">=" else lhs==q["rhs"]

def states(c: Mapping[str,Any]) -> Iterable[Dict[str,int]]:
    names=sorted(c["variables"])
    ranges=[range(c["variables"][n][0], c["variables"][n][1]+1) for n in names]
    for vals in itertools.product(*ranges):
        s=dict(zip(names,vals))
        if all(sat_constraint(q,s) for q in c["constraints"]): yield s

def canonical_paths(c: Mapping[str,Any]) -> List[Tuple[str,...]]:
    outgoing={n:[] for n in c["nodes"]}
    byid={e["id"]:e for e in c["edges"]}
    for e in c["edges"]: outgoing[e["src"]].append(e)
    for n in outgoing: outgoing[n].sort(key=lambda e:e["id"])
    out=[]
    def dfs(node:str, visited:set[str], edgeids:Tuple[str,...]):
        if node in c["bad_nodes"]:
            out.append(edgeids); return
        for e in outgoing[node]:
            if e["dst"] in visited: raise ValueError(f"{c['id']}: graph is cyclic")
            dfs(e["dst"], visited|{e["dst"]}, edgeids+(e["id"],))
    dfs(c["source_node"], {c["source_node"]}, ())
    return sorted(out)

def unsafe(c: Mapping[str,Any], s: Mapping[str,int], paths: Sequence[Tuple[str,...]]) -> bool:
    byid={e["id"]:e for e in c["edges"]}
    return any(all(s[byid[eid]["open_var"]]==1 for eid in p) for p in paths)

def ground_truth(c: Mapping[str,Any]) -> Tuple[str,int,int]:
    paths=canonical_paths(c); allowed=0; bad=0
    for s in states(c):
        allowed += 1
        if unsafe(c,s,paths): bad += 1
    if allowed==0: return "INCONSISTENT", allowed, bad
    return ("INSUFFICIENT" if bad else "PROVED"), allowed, bad

def max_linear_over_states(c: Mapping[str,Any], coeffs: Mapping[str,int]) -> int:
    vals=[sum(coeffs.get(x,0)*s[x] for x in c["variables"]) for s in states(c)]
    if not vals: raise ValueError("empty allowed state set")
    return max(vals)

def compact_method(c: Mapping[str,Any]) -> str:
    paths=canonical_paths(c); byid={e["id"]:e for e in c["edges"]}
    allowed=list(states(c))
    if not allowed: return "none"
    # Uniform zero edge: one edge on every bad path is zero over all states.
    zero={e["id"] for e in c["edges"] if all(s[e["open_var"]]==0 for s in allowed)}
    if paths and all(any(e in zero for e in p) for p in paths): return "uniform_cut"
    # Exact path-sum budget over the finite integer model.  This test enumerates
    # only in this independent oracle; the production path-budget certificate
    # carries arithmetic witnesses and does not enumerate states in its checker.
    for p in paths:
        coeffs={}
        for eid in p:
            v=byid[eid]["open_var"]; coeffs[v]=coeffs.get(v,0)+1
        if max_linear_over_states(c, coeffs) > len(p)-1: return "none"
    return "path_budget"


def _normalized_inequalities(c: Mapping[str,Any]) -> Dict[str,Tuple[Dict[str,Fraction],Fraction]]:
    out: Dict[str,Tuple[Dict[str,Fraction],Fraction]] = {}
    for q in c["constraints"]:
        a={x:Fraction(v) for x,v in q["coefficients"].items()}; b=Fraction(q["rhs"])
        if q["op"]=="<=": out[f"constraint:{q['id']}"]=(a,b)
        elif q["op"]==">=": out[f"constraint:{q['id']}"]=({x:-v for x,v in a.items()},-b)
        else:
            out[f"constraint+:{q['id']}"]=(a,b)
            out[f"constraint-:{q['id']}"]=({x:-v for x,v in a.items()},-b)
    for x,(lo,hi) in c["variables"].items():
        out[f"ub:{x}"]=({x:Fraction(1)},Fraction(hi))
        out[f"lb:{x}"]=({x:Fraction(-1)},Fraction(-lo))
    return out

def _f(q: Any) -> Fraction:
    if isinstance(q,int) and not isinstance(q,bool): return Fraction(q)
    if isinstance(q,str) and re.fullmatch(r'-?[0-9]+(?:/[1-9][0-9]*)?',q): return Fraction(q)
    raise ValueError(f"invalid exact multiplier {q!r}")

def check_linear_witness(c: Mapping[str,Any], target: Mapping[str,int], rhs: int, multipliers: Mapping[str,Any]) -> None:
    inequalities=_normalized_inequalities(c)
    acc={x:Fraction(0) for x in c["variables"]}; bound=Fraction(0)
    if not isinstance(multipliers,dict) or not multipliers: raise ValueError("empty witness")
    for key,raw in multipliers.items():
        if key not in inequalities: raise ValueError(f"unknown witness row {key}")
        m=_f(raw)
        if m<0: raise ValueError("negative multiplier")
        a,b=inequalities[key]
        for x,v in a.items(): acc[x]+=m*v
        bound+=m*b
    want={x:Fraction(target.get(x,0)) for x in c["variables"]}
    if acc!=want: raise ValueError(f"coefficient mismatch: {acc} != {want}")
    if bound>rhs: raise ValueError(f"bound {bound} does not prove <= {rhs}")

def check_compact_certificate(c: Mapping[str,Any]) -> str:
    cert=c["certificate"]
    if not isinstance(cert,dict) or "method" not in cert: raise ValueError("malformed certificate")
    method=cert["method"]
    paths=canonical_paths(c); byid={e["id"]:e for e in c["edges"]}
    if method=="none":
        if set(cert)!={"method"}: raise ValueError("extra fields in none certificate")
        return "none"
    if method=="uniform_cut":
        if set(cert)!={"method","cut_edges"}: raise ValueError("malformed cut certificate")
        cut=cert["cut_edges"]
        ids=[]
        for item in cut:
            if set(item)!={"edge_id","multipliers"}: raise ValueError("malformed cut item")
            eid=item["edge_id"]
            if eid not in byid or eid in ids: raise ValueError("unknown/duplicate cut edge")
            ids.append(eid); v=byid[eid]["open_var"]
            check_linear_witness(c,{v:1},0,item["multipliers"])
        if any(not any(e in ids for e in p) for p in paths): raise ValueError("cut misses canonical path")
        return method
    if method=="path_budget":
        if set(cert)!={"method","paths"}: raise ValueError("malformed path-budget certificate")
        items=cert["paths"]
        got=[]
        for item in items:
            if set(item)!={"edge_ids","multipliers"}: raise ValueError("malformed path item")
            pth=tuple(item["edge_ids"])
            if pth in got: raise ValueError("duplicate path certificate")
            got.append(pth)
            if pth not in paths: raise ValueError("noncanonical path certificate")
            coeffs={}
            for eid in pth:
                v=byid[eid]["open_var"]; coeffs[v]=coeffs.get(v,0)+1
            check_linear_witness(c,coeffs,len(pth)-1,item["multipliers"])
        if sorted(got)!=sorted(paths): raise ValueError("path certificate set is incomplete")
        return method
    raise ValueError(f"unknown certificate method {method}")

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path,default=Path(__file__).with_name("architecture_cases.json")); ap.add_argument("--output",type=Path)
    ns=ap.parse_args(); data=load_strict(ns.input)
    require_keys(data,ALLOWED_TOP,"top");
    if set(data)!=ALLOWED_TOP or data["schema"]!="tpeg-architecture-cases-v1": raise ValueError("bad schema")
    ids=set(); rows=[]
    for c in data["cases"]:
        validate_case(c)
        if c["id"] in ids: raise ValueError("duplicate case id")
        ids.add(c["id"])
        decision,allowed,bad=ground_truth(c); method=compact_method(c); certified=check_compact_certificate(c); paths=canonical_paths(c)
        if decision!=c["expected"]["ground_truth"] or method!=c["expected"]["compact_method"] or certified!=method:
            raise AssertionError(f"{c['id']}: got {(decision,method,certified)}, expected {c['expected']}")
        rows.append({"id":c["id"],"decision":decision,"compact_method":method,"certificate_method":certified,"allowed_states":allowed,"unsafe_states":bad,"bad_paths":len(paths)})
    result={"schema":"tpeg-architecture-case-results-v1","status":"PASS","case_count":len(rows),"cases":rows}
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if ns.output: ns.output.write_text(text,encoding="utf-8")
    else: print(text,end="")
    return 0
if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}",file=sys.stderr); raise
