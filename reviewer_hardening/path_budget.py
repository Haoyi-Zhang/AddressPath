"""Exact checker for compact path-budget certificates.

The checker is intentionally small and uses only Python's standard library.
It never trusts a producer's path list: all canonical source-to-bad paths are
recomputed, subject to an explicit fail-closed path cap.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple, FrozenSet, Any

Q = Fraction

class ModelError(ValueError):
    pass

class PathLimitExceeded(ModelError):
    pass


def q(value: Any) -> Q:
    if isinstance(value, bool):
        raise ModelError("booleans are not numeric coefficients")
    if isinstance(value, int):
        return Q(value)
    if isinstance(value, str):
        return Q(value)
    if isinstance(value, Mapping) and set(value) == {"num", "den"}:
        num=value["num"]; den=value["den"]
        if (not isinstance(num,int) or isinstance(num,bool) or
                not isinstance(den,int) or isinstance(den,bool)):
            raise ModelError("rational numerator and denominator must be exact integers")
        if den == 0:
            raise ModelError("rational denominator must be nonzero")
        return Q(num, den)
    raise ModelError(f"unsupported rational value: {value!r}")


def qjson(value: Q) -> dict:
    return {"num": value.numerator, "den": value.denominator}


def normalize_affine(obj: Mapping[str, Any], variables: Sequence[str] | set[str] | frozenset[str]) -> tuple[dict[str,Q],Q]:
    allowed = {"coeffs", "const"}
    if set(obj) - allowed:
        raise ModelError(f"unknown affine keys: {sorted(set(obj)-allowed)}")
    coeffs_raw = obj.get("coeffs", {})
    if not isinstance(coeffs_raw, Mapping):
        raise ModelError("coeffs must be an object")
    variable_set = variables if isinstance(variables,(set,frozenset)) else set(variables)
    if set(coeffs_raw) - variable_set:
        raise ModelError("affine expression mentions an unknown variable")
    coeffs = {}
    for v,raw in coeffs_raw.items():
        value=q(raw)
        if value:
            coeffs[v]=value
    return coeffs, q(obj.get("const", 0))


def add_affine(a: tuple[dict[str,Q],Q], b: tuple[dict[str,Q],Q]) -> tuple[dict[str,Q],Q]:
    av, ac = a; bv, bc = b
    out={}
    for v in set(av)|set(bv):
        value=av.get(v,Q(0))+bv.get(v,Q(0))
        if value:
            out[v]=value
    return out, ac+bc


def eval_affine(expr: tuple[dict[str,Q],Q], state: Mapping[str,int]) -> Q:
    coeffs, const = expr
    return const + sum((coef * state[v] for v,coef in coeffs.items()), Q(0))


@dataclass(frozen=True)
class Constraint:
    name: str
    coeffs: Mapping[str,Q]
    rhs: Q

@dataclass(frozen=True)
class Edge:
    name: str
    src: str
    dst: str
    open_expr: tuple[Mapping[str,Q],Q]

@dataclass(frozen=True)
class Model:
    name: str
    variables: Tuple[str,...]
    bounds: Mapping[str,Tuple[int,int]]
    nodes: Tuple[str,...]
    source: str
    bad: str
    constraints: Tuple[Constraint,...]
    edges: Tuple[Edge,...]


def parse_model(obj: Mapping[str,Any]) -> Model:
    required = {"name","variables","bounds","nodes","source","bad","constraints","edges"}
    if set(obj) != required:
        raise ModelError(f"model keys differ: missing={sorted(required-set(obj))}, extra={sorted(set(obj)-required)}")
    variables = tuple(obj["variables"])
    if not variables or len(set(variables)) != len(variables) or not all(isinstance(v,str) and v for v in variables):
        raise ModelError("variables must be unique nonempty strings")
    variable_set=set(variables)
    bounds_raw = obj["bounds"]
    if set(bounds_raw) != variable_set:
        raise ModelError("bounds must cover exactly the variables")
    bounds: dict[str,tuple[int,int]] = {}
    for v in variables:
        pair = bounds_raw[v]
        if not (isinstance(pair,list) and len(pair)==2 and all(isinstance(x,int) and not isinstance(x,bool) for x in pair)):
            raise ModelError("bounds must be integer [lo,hi] pairs")
        lo,hi=pair
        if lo>hi: raise ModelError("empty declared bound")
        bounds[v]=(lo,hi)
    nodes=tuple(obj["nodes"])
    if len(set(nodes))!=len(nodes) or not all(isinstance(n,str) and n for n in nodes):
        raise ModelError("nodes must be unique nonempty strings")
    source=obj["source"]; bad=obj["bad"]
    if source not in nodes or bad not in nodes or source==bad:
        raise ModelError("source and bad must be distinct graph nodes")
    constraints=[]
    names=set()
    for raw in obj["constraints"]:
        if set(raw)!={"name","coeffs","rhs"}: raise ModelError("bad constraint schema")
        name=raw["name"]
        if not isinstance(name,str) or not name or name in names: raise ModelError("constraint names must be unique")
        names.add(name)
        coeffs,const=normalize_affine({"coeffs":raw["coeffs"]},variable_set)
        if const: raise ModelError("constraint constant must be represented in rhs")
        constraints.append(Constraint(name,coeffs,q(raw["rhs"])))
    edges=[]; enames=set()
    for raw in obj["edges"]:
        if set(raw)!={"name","src","dst","open"}: raise ModelError("bad edge schema")
        name=raw["name"]
        if not isinstance(name,str) or not name or name in enames: raise ModelError("edge names must be unique")
        enames.add(name)
        if raw["src"] not in nodes or raw["dst"] not in nodes or raw["src"]==raw["dst"]:
            raise ModelError("bad edge endpoints")
        expr=normalize_affine(raw["open"],variable_set)
        edges.append(Edge(name,raw["src"],raw["dst"],expr))
    model=Model(obj["name"],variables,bounds,nodes,source,bad,tuple(constraints),tuple(edges))
    _topological_order(model)
    return model


def _topological_order(model: Model) -> tuple[str,...]:
    indeg={n:0 for n in model.nodes}; out={n:[] for n in model.nodes}
    for e in model.edges:
        indeg[e.dst]+=1; out[e.src].append(e.dst)
    ready=sorted(n for n,d in indeg.items() if d==0); order=[]
    while ready:
        n=ready.pop(0); order.append(n)
        for d in sorted(out[n]):
            indeg[d]-=1
            if indeg[d]==0:
                ready.append(d); ready.sort()
    if len(order)!=len(model.nodes): raise ModelError("graph must be acyclic")
    return tuple(order)


def canonical_paths(model: Model, cap: int=4096) -> tuple[tuple[str,...],...]:
    if cap < 1: raise ModelError("path cap must be positive")
    outgoing: dict[str,list[Edge]]={n:[] for n in model.nodes}
    for e in model.edges: outgoing[e.src].append(e)
    for es in outgoing.values(): es.sort(key=lambda e:e.name)
    paths: list[tuple[str,...]]=[]
    # Iterative depth-first traversal with one mutable path avoids quadratic
    # prefix copying on long chains while preserving deterministic order.
    stack: list[tuple[str,int]]=[(model.source,0)]
    current: list[str]=[]
    while stack:
        node,index=stack[-1]
        if node==model.bad:
            paths.append(tuple(current))
            if len(paths)>cap: raise PathLimitExceeded(f"more than {cap} source-to-bad paths")
            stack.pop()
            if current: current.pop()
            continue
        edges=outgoing[node]
        if index>=len(edges):
            stack.pop()
            if current: current.pop()
            continue
        edge=edges[index]
        stack[-1]=(node,index+1)
        current.append(edge.name)
        stack.append((edge.dst,0))
    return tuple(paths)


def allowed_states(model: Model, cap: int=1_000_000) -> Iterable[dict[str,int]]:
    sizes=1
    ranges=[]
    for v in model.variables:
        lo,hi=model.bounds[v]; sizes*=hi-lo+1
        if sizes>cap: raise ModelError(f"state space exceeds cap {cap}")
        ranges.append(range(lo,hi+1))
    for values in product(*ranges):
        s=dict(zip(model.variables,values))
        if all(sum((coef*s[v] for v,coef in c.coeffs.items()),Q(0)) <= c.rhs for c in model.constraints):
            yield s


def open_edges(model: Model, state: Mapping[str,int]) -> FrozenSet[str]:
    result=set()
    for e in model.edges:
        value=eval_affine(e.open_expr,state)
        if value not in (0,1): raise ModelError(f"edge {e.name} is not Boolean in an allowed state")
        if value==1: result.add(e.name)
    return frozenset(result)


def unsafe_state(model: Model, state: Mapping[str,int], path_cap: int=4096) -> bool:
    opened=open_edges(model,state)
    return any(all(e in opened for e in p) for p in canonical_paths(model,path_cap))


def oracle(model: Model, state_cap: int=1_000_000, path_cap: int=4096) -> dict:
    total=allowed=0; first_bad=None; signatures=set()
    for s in allowed_states(model,state_cap):
        allowed+=1; total+=1
        sig=open_edges(model,s); signatures.add(tuple(sorted(sig)))
        if first_bad is None and unsafe_state(model,s,path_cap): first_bad=dict(s)
    decision=("INCONSISTENT" if allowed==0 else ("PROVED" if first_bad is None else "INSUFFICIENT"))
    return {"allowed_states":allowed,"safe":allowed>0 and first_bad is None,"first_bad":first_bad,
            "signatures":len(signatures),"decision":decision}


def _path_affine(model: Model, path: Sequence[str]) -> tuple[dict[str,Q],Q]:
    emap={e.name:e for e in model.edges}
    coeffs: dict[str,Q]={}; const=Q(0)
    for name in path:
        if name not in emap: raise ModelError("certificate path mentions unknown edge")
        edge=emap[name]; const+=edge.open_expr[1]
        for variable,coefficient in edge.open_expr[0].items():
            value=coeffs.get(variable,Q(0))+coefficient
            if value: coeffs[variable]=value
            else: coeffs.pop(variable,None)
    return coeffs,const



def _validate_indicator_syntax(model: Model) -> None:
    """Require each non-enumerative edge indicator to be x or 1-x for a Boolean x."""
    for edge in model.edges:
        coeffs,const=edge.open_expr
        nonzero=[(v,c) for v,c in coeffs.items() if c]
        if len(nonzero)!=1:
            raise ModelError(f"edge {edge.name} is not a syntactic Boolean indicator")
        variable,coefficient=nonzero[0]
        if model.bounds[variable] != (0,1):
            raise ModelError(f"edge {edge.name} indicator variable is not Boolean-bounded")
        if not ((coefficient==Q(1) and const==Q(0)) or
                (coefficient==Q(-1) and const==Q(1))):
            raise ModelError(f"edge {edge.name} must be x or 1-x")


def _check_admitted_witness(model: Model, witness: Any) -> dict[str,int]:
    if not isinstance(witness, Mapping) or set(witness)!=set(model.variables):
        raise ModelError("witness must assign exactly all model variables")
    state: dict[str,int]={}
    for variable in model.variables:
        value=witness[variable]
        if not isinstance(value,int) or isinstance(value,bool):
            raise ModelError("witness values must be exact integers")
        lo,hi=model.bounds[variable]
        if value<lo or value>hi:
            raise ModelError("witness violates a declared bound")
        state[variable]=value
    for constraint in model.constraints:
        lhs=sum((coef*state[v] for v,coef in constraint.coeffs.items()),Q(0))
        if lhs>constraint.rhs:
            raise ModelError("witness violates an accounting constraint")
    # Also check the semantic Boolean value at the supplied admitted state.
    open_edges(model,state)
    return state

def check_certificate(model: Model, certificate: Mapping[str,Any], path_cap: int=4096) -> dict:
    if set(certificate)!={"type","model","witness","obligations"}: raise ModelError("bad certificate schema")
    if certificate["type"]!="path_budget" or certificate["model"]!=model.name:
        raise ModelError("certificate type or model mismatch")
    _validate_indicator_syntax(model)
    _check_admitted_witness(model,certificate["witness"])
    paths=canonical_paths(model,path_cap)
    obligations=certificate["obligations"]
    if not isinstance(obligations,list): raise ModelError("obligations must be a list")
    by_path={}
    for ob in obligations:
        if set(ob)!={"path","multipliers"}: raise ModelError("bad obligation schema")
        path=tuple(ob["path"])
        if path in by_path: raise ModelError("duplicate path obligation")
        if not isinstance(ob["multipliers"],Mapping): raise ModelError("multipliers must be an object")
        by_path[path]=ob["multipliers"]
    if set(by_path)!=set(paths):
        missing=set(paths)-set(by_path); extra=set(by_path)-set(paths)
        raise ModelError(f"obligations do not equal canonical path set: missing={len(missing)} extra={len(extra)}")
    cmap={c.name:c for c in model.constraints}
    for path in paths:
        if not path: raise ModelError("empty source-to-bad path is unsupported")
        target_coeffs,target_const=_path_affine(model,path)
        combo={}; combo_rhs=Q(0)
        for name,raw_lam in by_path[path].items():
            if name not in cmap: raise ModelError("unknown constraint in multiplier map")
            lam=q(raw_lam)
            if lam<0: raise ModelError("multipliers must be nonnegative")
            c=cmap[name]
            for v,coef in c.coeffs.items():
                value=combo.get(v,Q(0))+lam*coef
                if value:
                    combo[v]=value
                else:
                    combo.pop(v,None)
            combo_rhs+=lam*c.rhs
        if combo != target_coeffs:
            raise ModelError(f"coefficient mismatch for path {path}")
        if target_const + combo_rhs > Q(len(path)-1):
            raise ModelError(f"insufficient bound for path {path}")
    return {"status":"PROVED","method":"path_budget","paths":len(paths)}


def make_alternating_model(n: int, name: str|None=None) -> tuple[dict,dict]:
    if n<1: raise ValueError("n must be positive")
    variables=[]; bounds={}; constraints=[]; edges=[]; nodes=[f"v{i}" for i in range(2*n+1)]
    for i in range(n):
        x=f"x{i}"; y=f"y{i}"; variables += [x,y]; bounds[x]=[0,1]; bounds[y]=[0,1]
        constraints.append({"name":f"pair_{i}","coeffs":{x:1,y:1},"rhs":1})
        edges.append({"name":f"e{i}_x","src":nodes[2*i],"dst":nodes[2*i+1],"open":{"coeffs":{x:1},"const":0}})
        edges.append({"name":f"e{i}_y","src":nodes[2*i+1],"dst":nodes[2*i+2],"open":{"coeffs":{y:1},"const":0}})
    model={"name":name or f"alternating_{n}","variables":variables,"bounds":bounds,"nodes":nodes,
           "source":nodes[0],"bad":nodes[-1],"constraints":constraints,"edges":edges}
    cert={"type":"path_budget","model":model["name"],
          "witness":{v:0 for v in variables},
          "obligations":[{
        "path":[e["name"] for e in edges],
        "multipliers":{f"pair_{i}":1 for i in range(n)}
    }]}
    return model,cert


def make_unsafe_model(n: int, name: str|None=None) -> dict:
    m,_=make_alternating_model(n,name or f"unsafe_{n}")
    m["constraints"]=[]
    return m


def make_integer_only_model(name: str="integer_only") -> dict:
    return {"name":name,"variables":["z"],"bounds":{"z":[0,1]},"nodes":["s","b"],"source":"s","bad":"b",
            "constraints":[{"name":"half","coeffs":{"z":2},"rhs":1}],
            "edges":[{"name":"e","src":"s","dst":"b","open":{"coeffs":{"z":1},"const":0}}]}


def max_signatures(model: Model, state_cap: int=1_000_000) -> tuple[FrozenSet[str],...]:
    sigs={open_edges(model,s) for s in allowed_states(model,state_cap)}
    maxima=[s for s in sigs if not any(s<t for t in sigs)]
    return tuple(sorted(maxima,key=lambda s:(len(s),tuple(sorted(s)))))
