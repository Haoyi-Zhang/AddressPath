"""Deterministic benign diagnostic cases; no hardware schema or probe is copied."""
from fractions import Fraction as F
from pathlib import Path
import json,random

def add(nodes,terms,constant=0):
    nodes.append({'constant':str(constant),'terms':[[i,str(w)] for i,w in terms]});return len(nodes)-1

def obs(node,lo,hi):return {'node':node,'lower':str(lo),'upper':str(hi)}
def model(family,bounds,nodes,observations,prop,upper=0,assumptions=None):
    return {'id':'','family':family,'domain':{'kind':'integer_grid','bounds':bounds},'nodes':nodes,
            'observations':observations,'assumptions':assumptions or [],'assertion':{'node':prop,'upper':str(upper)}}
def all_cases():
    out=[]
    for n in range(1,5):
        for w in [F(0),F(1,4),F(3,4),F(1),F(5,4)]:
            nodes=[{'input':0},{'input':1}];total=add(nodes,[(0,1),(1,1)])
            out.append(model('accounting',[[0,n],[0,n]],nodes,[obs(total,n,n),obs(0,n-w,n+w)],1))
    for n in range(1,5):
        for scale in [F(1),F(1,3)]:
            nodes=[{'input':0},{'input':1}];total=add(nodes,[(0,scale),(1,scale)])
            out.append(model('signature_alias',[[0,n],[0,n]],nodes,[obs(total,scale*n,scale*n)],1))
    for n in [1,2]:
        for w in [F(0),F(1,4),F(1)]:
            for keep in [True,False]:
                nodes=[{'input':0},{'input':1},{'input':2}]
                total=add(nodes,[(0,1),(1,1),(2,1)])
                accounted=add(nodes,[(0,1),(2,1)])
                residual=add(nodes,[(total,1),(accounted,-1)])
                observations=[obs(total,n,n),obs(accounted,0,2*n)]
                if keep:observations.append(obs(residual,-w,w))
                out.append(model('correlated' if keep else 'marginal_only',[[0,n]]*3,nodes,observations,1))
    for n in range(1,5):
        nodes=[{'input':0},{'input':1}];total=add(nodes,[(0,1),(1,1)])
        out.append(model('inconsistent',[[0,n+2],[0,n+2]],nodes,[obs(total,n,n),obs(0,n+1,n+2)],1))
    for odd in [3,5,7]:
        nodes=[{'input':0},{'input':1}];weighted=add(nodes,[(0,2),(1,odd)])
        out.append(model('one_cut_gap',[[0,(odd+1)//2],[0,2]],nodes,[obs(weighted,odd+1,odd+1)],1))
    for scale in [F(1),F(1,3),F(7)]:
        nodes=[{'input':0}];weighted=add(nodes,[(0,2*scale)])
        out.append(model('lattice_empty',[[0,1]],nodes,[obs(weighted,scale,scale)],0))
    for bits in [8,32,128]:
        for sign in [-1,1]:
            w=F(1)+sign*F(1,2**bits)
            nodes=[{'input':0},{'input':1}];total=add(nodes,[(0,1),(1,1)])
            out.append(model('strict_boundary',[[0,2],[0,2]],nodes,[obs(total,2,2),obs(0,2-w,2+w)],1))
    for constrained in [True,False]:
        nodes=[{'input':0},{'input':1},{'input':2}]
        out.append(model('state_ceiling',[[0,15]]*3,nodes,[obs(2,0,0)] if constrained else [],2))
    rng=random.Random(20260913)
    for _ in range(24):
        n=rng.randint(2,4);nodes=[{'input':0},{'input':1}];p=[rng.randint(0,n),rng.randint(0,n)]
        observations=[]
        for __ in range(2):
            a=[rng.randint(0,3),rng.randint(0,3)]
            idx=add(nodes,list(enumerate(a)));y=sum(x*w for x,w in zip(p,a));w=F(rng.randint(0,3),2)
            observations.append(obs(idx,y-w,y+w))
        a=[rng.randint(0,2),rng.randint(0,2)]
        prop=add(nodes,list(enumerate(a)));upper=sum(x*w for x,w in zip(p,a))+rng.randint(-1,2)
        out.append(model('seeded_affine',[[0,n],[0,n]],nodes,observations,prop,upper))
    # Degenerate and affine-offset controls exercise the proof rule, not a CPU.
    nodes=[{'input':0}];p=add(nodes,[],0)
    out.append(model('constant_assertion',[[0,2]],nodes,[],p))
    nodes=[{'input':0}];p=add(nodes,[],1)
    out.append(model('constant_assertion',[[0,2]],nodes,[],p))
    nodes=[{'input':0}];p=add(nodes,[(0,F(2,3))],F(1,3))
    out.append(model('affine_quantum',[[0,2]],nodes,[obs(0,0,F(1,4))],p,F(1,3)))
    nodes=[{'input':0}]
    out.append(model('reversed_interval',[[0,2]],nodes,[obs(0,2,1)],0))
    for i,m in enumerate(out):m['id']=f'case-{i+1:03}'
    return out

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='cases');args=ap.parse_args()
    dest=Path(args.output);dest.mkdir(parents=True,exist_ok=True)
    for m in all_cases():(dest/(m['id']+'.json')).write_text(json.dumps(m,indent=2)+'\n')
    print(f'{len(all_cases())} models written to {dest}')
