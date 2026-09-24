#!/usr/bin/env python3
"""Validate the explicit-path complexity boundary and fail-closed cap behavior."""
from __future__ import annotations
import csv,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
CAP=4096

def graph(depth):
    # Each layer offers two edge-distinct branches that rejoin, yielding 2^depth paths.
    nodes=['s']; edges=[]; cur='s'
    for i in range(depth):
        a=f'a{i}'; b=f'b{i}'; j=f'j{i}'
        nodes += [a,b,j]
        edges += [(f'e{i}a0',cur,a),(f'e{i}a1',a,j),(f'e{i}b0',cur,b),(f'e{i}b1',b,j)]
        cur=j
    nodes.append('bad'); edges.append(('e_bad',cur,'bad'))
    return nodes,edges

def enumerate_paths(depth,cap=CAP):
    nodes,edges=graph(depth); out={n:[] for n in nodes}
    for eid,s,d in edges: out[s].append((eid,d))
    for n in out: out[n].sort()
    paths=[]
    def dfs(n,es):
        if len(paths)>cap: return
        if n=='bad': paths.append(tuple(es)); return
        for eid,d in out[n]: dfs(d,es+[eid])
    dfs('s',[])
    if len(paths)>cap: raise OverflowError(f'canonical path cap {cap} exceeded')
    return paths

def main():
    rows=[]
    for d in range(1,14):
        want=2**d; status='PASS'
        try: got=len(enumerate_paths(d))
        except OverflowError:
            got=None; status='REJECTED_AT_CAP'
        if want<=CAP:
            assert status=='PASS' and got==want
        else:
            assert status=='REJECTED_AT_CAP'
        rows.append({'depth':d,'closed_form_paths':want,'cap':CAP,'enumerated_paths':got if got is not None else '', 'status':status})
    with (HERE/'path_enumeration_boundary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (HERE/'path_enumeration_boundary.json').write_text(json.dumps({'schema':'path-enumeration-boundary-v1','status':'PASS','cap':CAP,'largest_accepted_depth':12,'first_rejected_depth':13},indent=2,sort_keys=True)+'\n')
if __name__=='__main__': main()
