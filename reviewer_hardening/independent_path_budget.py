"""Second implementation of path-budget checking.

This module deliberately does not import reviewer_hardening.path_budget.
It is used as an implementation-diversity check, not as a formally verified
checker.
"""
from __future__ import annotations
from fractions import Fraction
from itertools import product
from typing import Any, Mapping

class IndependentError(ValueError): pass

def F(x: Any) -> Fraction:
    if isinstance(x,bool): raise IndependentError("bool is not a number")
    if isinstance(x,int): return Fraction(x)
    if isinstance(x,str): return Fraction(x)
    if isinstance(x,dict) and set(x)=={"num","den"}: return Fraction(int(x["num"]),int(x["den"]))
    raise IndependentError("invalid rational")

def _vars(m):
    vs=m.get("variables")
    if not isinstance(vs,list) or not vs or len(vs)!=len(set(vs)): raise IndependentError("invalid variables")
    return tuple(vs)

def _dag_paths(m,limit=4096):
    nodes=m["nodes"]; source=m["source"]; bad=m["bad"]
    if len(nodes)!=len(set(nodes)) or source not in nodes or bad not in nodes: raise IndependentError("bad graph")
    adj={n:[] for n in nodes}; indeg={n:0 for n in nodes}; edge_by_name={}
    for e in m["edges"]:
        if set(e)!={"name","src","dst","open"}: raise IndependentError("bad edge")
        if e["name"] in edge_by_name: raise IndependentError("duplicate edge")
        if e["src"] not in adj or e["dst"] not in adj: raise IndependentError("unknown endpoint")
        edge_by_name[e["name"]]=e; adj[e["src"]].append(e); indeg[e["dst"]]+=1
    q=sorted([n for n in nodes if indeg[n]==0]); seen=[]
    while q:
        x=q.pop(0); seen.append(x)
        for e in sorted(adj[x],key=lambda z:z["name"]):
            indeg[e["dst"]]-=1
            if indeg[e["dst"]]==0: q.append(e["dst"]); q.sort()
    if len(seen)!=len(nodes): raise IndependentError("cycle")
    paths=[]; stack=[(source,())]
    while stack:
        n,p=stack.pop()
        if n==bad:
            paths.append(p)
            if len(paths)>limit: raise IndependentError("path limit")
        else:
            for e in sorted(adj[n],key=lambda z:z["name"],reverse=True):
                stack.append((e["dst"],p+(e["name"],)))
    return tuple(sorted(paths)),edge_by_name

def _affine(raw,vs):
    if set(raw)-{"coeffs","const"}: raise IndependentError("unknown affine field")
    c=raw.get("coeffs",{})
    if set(c)-set(vs): raise IndependentError("unknown variable")
    return {v:F(c.get(v,0)) for v in vs},F(raw.get("const",0))

def check(m: Mapping[str,Any], cert: Mapping[str,Any], limit=4096):
    required={"name","variables","bounds","nodes","source","bad","constraints","edges"}
    if set(m)!=required: raise IndependentError("model schema")
    vs=_vars(m); paths,emap=_dag_paths(m,limit)
    if set(cert)!={"type","model","obligations"} or cert["type"]!="path_budget" or cert["model"]!=m["name"]:
        raise IndependentError("certificate schema")
    cons={}
    for c in m["constraints"]:
        if set(c)!={"name","coeffs","rhs"} or c["name"] in cons: raise IndependentError("constraint schema")
        if set(c["coeffs"])-set(vs): raise IndependentError("constraint variable")
        cons[c["name"]]=({v:F(c["coeffs"].get(v,0)) for v in vs},F(c["rhs"]))
    obs={}
    for o in cert["obligations"]:
        if set(o)!={"path","multipliers"}: raise IndependentError("obligation schema")
        p=tuple(o["path"])
        if p in obs: raise IndependentError("duplicate obligation")
        obs[p]=o["multipliers"]
    if set(obs)!=set(paths): raise IndependentError("path coverage")
    for p in paths:
        target={v:Fraction(0) for v in vs}; const=Fraction(0)
        for en in p:
            co,k=_affine(emap[en]["open"],vs); const+=k
            for v in vs: target[v]+=co[v]
        got={v:Fraction(0) for v in vs}; rhs=Fraction(0)
        for cn,lv in obs[p].items():
            if cn not in cons: raise IndependentError("unknown constraint")
            lam=F(lv)
            if lam<0: raise IndependentError("negative multiplier")
            co,b=cons[cn]
            for v in vs: got[v]+=lam*co[v]
            rhs+=lam*b
        if got!=target or const+rhs>len(p)-1: raise IndependentError("invalid linear certificate")
    return {"status":"PROVED","paths":len(paths)}

def oracle(m: Mapping[str,Any], state_limit=1_000_000, path_limit=4096):
    vs=_vars(m); paths,emap=_dag_paths(m,path_limit)
    ranges=[]; total=1
    for v in vs:
        b=m["bounds"][v]
        if not (isinstance(b,list) and len(b)==2 and all(isinstance(x,int) and not isinstance(x,bool) for x in b)): raise IndependentError("bad bounds")
        total*=b[1]-b[0]+1
        if total>state_limit: raise IndependentError("state limit")
        ranges.append(range(b[0],b[1]+1))
    allowed=0; bad_state=None
    for vals in product(*ranges):
        s=dict(zip(vs,vals))
        good=True
        for c in m["constraints"]:
            if sum(F(c["coeffs"].get(v,0))*s[v] for v in vs)>F(c["rhs"]): good=False; break
        if not good: continue
        allowed+=1; opened=set()
        for en,e in emap.items():
            co,k=_affine(e["open"],vs); val=k+sum(co[v]*s[v] for v in vs)
            if val not in (0,1): raise IndependentError("nonboolean edge")
            if val==1: opened.add(en)
        if any(all(en in opened for en in p) for p in paths):
            bad_state=s; break
    return {"allowed_states":allowed,"safe":bad_state is None,"first_bad":bad_state}
