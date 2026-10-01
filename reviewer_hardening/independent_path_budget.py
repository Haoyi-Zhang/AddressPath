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
    if isinstance(x,dict) and set(x)=={"num","den"}:
        num=x["num"]; den=x["den"]
        if (not isinstance(num,int) or isinstance(num,bool) or
                not isinstance(den,int) or isinstance(den,bool) or den==0):
            raise IndependentError("rational components must be exact integers and denominator nonzero")
        return Fraction(num,den)
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
    for edges in adj.values(): edges.sort(key=lambda z:z["name"])
    q=sorted([n for n in nodes if indeg[n]==0]); seen=[]
    while q:
        x=q.pop(0); seen.append(x)
        for e in adj[x]:
            indeg[e["dst"]]-=1
            if indeg[e["dst"]]==0: q.append(e["dst"]); q.sort()
    if len(seen)!=len(nodes): raise IndependentError("cycle")
    paths=[]; stack=[(source,0)]; current=[]
    while stack:
        n,index=stack[-1]
        if n==bad:
            paths.append(tuple(current))
            if len(paths)>limit: raise IndependentError("path limit")
            stack.pop()
            if current: current.pop()
            continue
        edges=adj[n]
        if index>=len(edges):
            stack.pop()
            if current: current.pop()
            continue
        edge=edges[index]; stack[-1]=(n,index+1)
        current.append(edge["name"]); stack.append((edge["dst"],0))
    return tuple(paths),edge_by_name

def _affine(raw,vs,vset=None):
    if set(raw)-{"coeffs","const"}: raise IndependentError("unknown affine field")
    c=raw.get("coeffs",{})
    if set(c)-(vset if vset is not None else set(vs)): raise IndependentError("unknown variable")
    out={}
    for v,raw_value in c.items():
        value=F(raw_value)
        if value: out[v]=value
    return out,F(raw.get("const",0))

def check(m: Mapping[str,Any], cert: Mapping[str,Any], limit=4096):
    required={"name","variables","bounds","nodes","source","bad","constraints","edges"}
    if set(m)!=required: raise IndependentError("model schema")
    vs=_vars(m); vset=set(vs); paths,emap=_dag_paths(m,limit)
    if set(cert)!={"type","model","witness","obligations"} or cert["type"]!="path_budget" or cert["model"]!=m["name"]:
        raise IndependentError("certificate schema")
    bounds={}
    if set(m["bounds"])!=set(vs): raise IndependentError("bounds coverage")
    for v in vs:
        b=m["bounds"][v]
        if not (isinstance(b,list) and len(b)==2 and all(isinstance(x,int) and not isinstance(x,bool) for x in b) and b[0]<=b[1]):
            raise IndependentError("bad bounds")
        bounds[v]=(b[0],b[1])
    cons={}
    for c in m["constraints"]:
        if set(c)!={"name","coeffs","rhs"} or c["name"] in cons: raise IndependentError("constraint schema")
        if set(c["coeffs"])-vset: raise IndependentError("constraint variable")
        sparse={}
        for v,raw_value in c["coeffs"].items():
            value=F(raw_value)
            if value: sparse[v]=value
        cons[c["name"]]=(sparse,F(c["rhs"]))
    # Syntactically guarantee Boolean indicators without enumerating the state space.
    for en,e in emap.items():
        co,k=_affine(e["open"],vs,vset); nz=[(v,a) for v,a in co.items() if a]
        if len(nz)!=1 or bounds[nz[0][0]]!=(0,1) or not ((nz[0][1]==1 and k==0) or (nz[0][1]==-1 and k==1)):
            raise IndependentError(f"edge {en} is not x or 1-x over a Boolean variable")
    witness=cert["witness"]
    if not isinstance(witness,Mapping) or set(witness)!=set(vs): raise IndependentError("witness coverage")
    state={}
    for v in vs:
        value=witness[v]
        if not isinstance(value,int) or isinstance(value,bool) or not (bounds[v][0]<=value<=bounds[v][1]):
            raise IndependentError("bad witness value")
        state[v]=value
    for co,rhs in cons.values():
        if sum(a*state[v] for v,a in co.items())>rhs: raise IndependentError("witness violates constraints")
    for e in emap.values():
        co,k=_affine(e["open"],vs,vset); val=k+sum(a*state[v] for v,a in co.items())
        if val not in (0,1): raise IndependentError("witness has nonboolean edge")
    obs={}
    for o in cert["obligations"]:
        if set(o)!={"path","multipliers"}: raise IndependentError("obligation schema")
        p=tuple(o["path"])
        if p in obs: raise IndependentError("duplicate obligation")
        obs[p]=o["multipliers"]
    if set(obs)!=set(paths): raise IndependentError("path coverage")
    for p in paths:
        target={}; const=Fraction(0)
        for en in p:
            co,k=_affine(emap[en]["open"],vs,vset); const+=k
            for v,a in co.items():
                value=target.get(v,Fraction(0))+a
                if value: target[v]=value
                else: target.pop(v,None)
        got={}; rhs=Fraction(0)
        for cn,lv in obs[p].items():
            if cn not in cons: raise IndependentError("unknown constraint")
            lam=F(lv)
            if lam<0: raise IndependentError("negative multiplier")
            co,b=cons[cn]
            for v,a in co.items():
                value=got.get(v,Fraction(0))+lam*a
                if value: got[v]=value
                else: got.pop(v,None)
            rhs+=lam*b
        if got!=target or const+rhs>len(p)-1: raise IndependentError("invalid linear certificate")
    return {"status":"PROVED","paths":len(paths)}

def oracle(m: Mapping[str,Any], state_limit=1_000_000, path_limit=4096):
    vs=_vars(m); vset=set(vs); paths,emap=_dag_paths(m,path_limit)
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
            if sum(F(a)*s[v] for v,a in c["coeffs"].items())>F(c["rhs"]): good=False; break
        if not good: continue
        allowed+=1; opened=set()
        for en,e in emap.items():
            co,k=_affine(e["open"],vs,vset); val=k+sum(a*s[v] for v,a in co.items())
            if val not in (0,1): raise IndependentError("nonboolean edge")
            if val==1: opened.add(en)
        if any(all(en in opened for en in p) for p in paths):
            bad_state=s; break
    decision=("INCONSISTENT" if allowed==0 else ("PROVED" if bad_state is None else "INSUFFICIENT"))
    return {"allowed_states":allowed,"safe":allowed>0 and bad_state is None,"first_bad":bad_state,"decision":decision}
