"""Bounded exact proposal engine. Untrusted by checker.py.

The mathematical baseline is small-dimensional vertex/support enumeration,
not a new LP algorithm. It never emits a property-violating state.
"""
from fractions import Fraction as Q
from itertools import combinations, product
from math import gcd, lcm

class Exhausted(RuntimeError):
    pass

class Work:
    def __init__(self, cap=20000):
        self.systems=0; self.cap=cap
    def tick(self):
        self.systems+=1
        if self.systems>self.cap: raise Exhausted('basis enumeration cap')

def frac(x): return Q(x)
def serial(x): return str(x.numerator) if x.denominator == 1 else str(x)
def dot(a,b): return sum((x*y for x,y in zip(a,b)), Q())

def translate(model):
    d=len(model['domain']['bounds'])
    coeff=[]; offs=[]
    for node in model['nodes']:
        if 'input' in node:
            coeff.append([Q(j==node['input']) for j in range(d)]); offs.append(Q())
        else:
            a=[Q() for _ in range(d)]; b=frac(node['constant'])
            for idx,w in node['terms']:
                w=frac(w)
                for j in range(d): a[j]+=w*coeff[idx][j]
                b+=w*offs[idx]
            coeff.append(a); offs.append(b)
    rows=[]; rhs=[]
    for j,(lo,hi) in enumerate(model['domain']['bounds']):
        lower=[Q() for _ in range(d)]; lower[j]=-1
        upper=[-x for x in lower]
        rows.extend([lower,upper]); rhs.extend([Q(-lo),Q(hi)])
    for obs in model['assumptions']+model['observations']:
        idx=obs['node']; a=coeff[idx]; b=offs[idx]
        rows.extend([[-x for x in a],a.copy()])
        rhs.extend([b-frac(obs['lower']), frac(obs['upper'])-b])
    idx=model['assertion']['node']
    return rows,rhs,coeff[idx],offs[idx]-frac(model['assertion']['upper'])

def solve(M, target, work):
    """Unique solution to a possibly overdetermined rational system."""
    work.tick()
    n=len(M[0]) if M else 0
    aug=[list(map(Q,row))+[Q(t)] for row,t in zip(M,target)]
    r=0; pivots=[]
    for col in range(n):
        pivot=next((i for i in range(r,len(aug)) if aug[i][col]),None)
        if pivot is None: return None
        aug[r],aug[pivot]=aug[pivot],aug[r]
        f=aug[r][col]; aug[r]=[v/f for v in aug[r]]
        for i in range(len(aug)):
            if i != r and aug[i][col]:
                f=aug[i][col]; aug[i]=[v-f*w for v,w in zip(aug[i],aug[r])]
        pivots.append(col); r+=1
    if any(all(v==0 for v in row[:-1]) and row[-1]!=0 for row in aug): return None
    return [aug[i][-1] for i in range(n)]

def optimize_vertices(A,b,c,q0,work):
    d=len(c); best=None; vertex_count=0; first=None
    for ids in combinations(range(len(A)), d):
        x=solve([A[i] for i in ids],[b[i] for i in ids],work)
        if x is not None and all(dot(row,x)<=v for row,v in zip(A,b)):
            vertex_count+=1
            if first is None: first=x
            score=dot(c,x)+q0
            if best is None or score>best: best=score
    return best,vertex_count,first

def dual_bound(A,b,c,q0,work):
    d=len(c); m=len(A)
    if not any(c): return q0,[Q()]*m
    best=None; multipliers=None
    for k in range(1,d+1):
        for ids in combinations(range(m),k):
            lam=solve([[A[i][j] for i in ids] for j in range(d)],c,work)
            if lam is not None and all(v>=0 for v in lam):
                value=sum((v*b[i] for v,i in zip(lam,ids)),Q())+q0
                if best is None or value<best:
                    best=value; multipliers=[Q()]*m
                    for i,v in zip(ids,lam): multipliers[i]=v
    return best,multipliers

def inconsistent(A,b,work):
    d=len(A[0]);m=len(A)
    for k in range(1,d+2):
        for ids in combinations(range(m),k):
            mat=[[A[i][j] for i in ids] for j in range(d)]+[[b[i] for i in ids]]
            lam=solve(mat,[Q()]*d+[Q(-1)],work)
            if lam is not None and all(v>=0 for v in lam):
                out=[Q()]*m
                for i,v in zip(ids,lam): out[i]=v
                return out
    return None

def finite_cover(model,A,b,c,q0):
    cover=[];witness=None;positive=False;accepted=0
    for z in product(*(range(lo,hi+1) for lo,hi in model['domain']['bounds'])):
        badrow=next((i for i,(row,v) in enumerate(zip(A,b)) if dot(row,z)>v),None)
        if badrow is not None: cover.append(badrow)
        else:
            accepted+=1
            if witness is None: witness=list(z)
            if dot(c,z)+q0>0: positive=True
            cover.append(-1)
    if positive: return 'INSUFFICIENT',witness,None,accepted
    status='PROVED' if witness is not None else 'INCONSISTENT'
    return status,witness,{'kind':'finite_cover','decision':status,'witness':witness,'cover':cover},accepted

def make(model,cap=20000):
    A,b,c,q0=translate(model);work=Work(cap)
    status,witness,cover,count=finite_cover(model,A,b,c,q0)
    relaxed,vertices,_=optimize_vertices(A,b,c,q0,work)
    bound,lam=(None,None) if relaxed is None else dual_bound(A,b,c,q0,work)
    if relaxed is not None and bound!=relaxed:
        raise AssertionError('primal/dual exact objective disagreement')
    linear='INSUFFICIENT';quantized='INSUFFICIENT';cert=None
    if relaxed is None:
        mult=inconsistent(A,b,work)
        if mult is None: raise AssertionError('no inconsistency certificate')
        cert={'kind':'inconsistent','multipliers':[serial(v) for v in mult]}
        linear=quantized='INCONSISTENT'
    elif witness is not None:
        if bound<=0:
            linear=quantized='PROVED';cert={'kind':'linear','witness':witness,'multipliers':[serial(v) for v in lam]}
        else:
            vals=c+[q0];den=lcm(*(v.denominator for v in vals))
            num=gcd(*(abs(int(v*den)) for v in vals)); delta=Q(num,den)
            if delta and bound<delta:
                quantized='PROVED';cert={'kind':'quantized','witness':witness,'multipliers':[serial(v) for v in lam]}
    # Exhaustive fallback is clearly distinguished from the dual proof.
    if cert is None and status!='INSUFFICIENT': cert=cover
    return {'exact_status':status,'linear_status':linear,'quantized_status':quantized,
            'relaxed_upper':None if bound is None else serial(bound),
            'feasible_finite_states':count,'basis_systems':work.systems,
            'feasible_vertex_bases':vertices,'certificate':cert}
