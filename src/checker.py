"""Exact proof checker for finite integer-grid, rational-linear accounting DAGs.

No optimizer is imported. A certificate is checked against the supplied model,
not against any model or numeric answer stored in the certificate.
"""
from __future__ import annotations
from fractions import Fraction as F
from itertools import product
from math import gcd, lcm, prod
import json
import re
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_BITS = 512
MAX_STATES = 4096

class Invalid(ValueError):
    pass

def rational(x: Any) -> F:
    if type(x) is int:
        v = F(x)
    elif type(x) is str and len(x) <= 320:
        # Only integer or numerator/positive-denominator literals are admitted.
        parts = x.split('/')
        if len(parts) not in (1, 2) or not all(re.fullmatch(r'-?[0-9]+', p) for p in parts):
            raise Invalid('invalid rational literal')
        if len(parts) == 2 and (parts[1].startswith('-') or int(parts[1]) <= 0):
            raise Invalid('denominator must be positive')
        v = F(x)
    else:
        raise Invalid('rationals must be integers or rational strings, never floats')
    if max(v.numerator.bit_length(), v.denominator.bit_length()) > MAX_BITS:
        raise Invalid('rational input exceeds bit budget')
    return v

def integer(x: Any, lo: int, hi: int) -> int:
    if type(x) is not int or not lo <= x <= hi:
        raise Invalid('integer outside admitted range')
    return x

def _keys(o: Any, expected: set[str]) -> None:
    if type(o) is not dict or set(o) != expected:
        raise Invalid('missing, duplicate, or unexpected fields')

def _pairs(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise Invalid('duplicate JSON key')
        obj[k] = v
    return obj

def load(path: str | Path) -> Any:
    path = Path(path)
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise Invalid('input exceeds byte budget')
        return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_pairs,
                          parse_float=lambda _: (_ for _ in ()).throw(Invalid('float literal')),
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid('nonfinite literal')))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Invalid('unreadable JSON') from exc

def dot(a, b):
    return sum((u*v for u, v in zip(a, b)), F(0))

def compile_model(model: Any):
    _keys(model, {'id', 'family', 'domain', 'nodes', 'observations', 'assumptions', 'assertion'})
    if type(model['id']) is not str or len(model['id']) > 64:
        raise Invalid('invalid model id')
    if type(model['family']) is not str or len(model['family']) > 64:
        raise Invalid('invalid family')
    dom = model['domain']
    _keys(dom, {'kind', 'bounds'})
    if dom['kind'] != 'integer_grid' or type(dom['bounds']) is not list:
        raise Invalid('only declared finite integer grids are admitted')
    d = len(dom['bounds'])
    if not 1 <= d <= 16:
        raise Invalid('input dimension')
    bounds = []
    for v in dom['bounds']:
        if type(v) is not list or len(v) != 2:
            raise Invalid('input bound shape')
        lo, hi = integer(v[0], -4096, 4096), integer(v[1], -4096, 4096)
        if lo > hi:
            raise Invalid('empty input range is malformed, not a proof')
        bounds.append((lo, hi))
    if prod(hi-lo+1 for lo, hi in bounds) > MAX_STATES:
        raise Invalid('finite state budget')
    nodes = model['nodes']
    if type(nodes) is not list or not d <= len(nodes) <= 64:
        raise Invalid('node budget')
    forms = []
    for i, node in enumerate(nodes):
        if i < d:
            _keys(node, {'input'})
            if integer(node['input'], 0, d-1) != i:
                raise Invalid('canonical input order required')
            forms.append(([F(int(j == i)) for j in range(d)], F(0)))
        else:
            _keys(node, {'constant', 'terms'})
            if type(node['terms']) is not list or len(node['terms']) > 64:
                raise Invalid('term budget')
            vec, off = [F(0)]*d, rational(node['constant'])
            seen = set()
            for term in node['terms']:
                if type(term) is not list or len(term) != 2:
                    raise Invalid('term shape')
                parent = integer(term[0], 0, i-1)
                if parent in seen:
                    raise Invalid('duplicate parent')
                seen.add(parent)
                coeff = rational(term[1])
                pv, pc = forms[parent]
                vec = [a+coeff*b for a, b in zip(vec, pv)]
                off += coeff*pc
            if any(max(v.numerator.bit_length(), v.denominator.bit_length()) > 4096 for v in [*vec, off]):
                raise Invalid('compiled arithmetic exceeds bit budget')
            forms.append((vec, off))
    A, b = [], []
    for j, (lo, hi) in enumerate(bounds):
        v = [F(0)]*d; v[j] = -1
        A.append(v); b.append(F(-lo))
        v = [F(0)]*d; v[j] = 1
        A.append(v); b.append(F(hi))
    for field, cap in [('assumptions', 128), ('observations', 16)]:
        entries = model[field]
        if type(entries) is not list or len(entries) > cap:
            raise Invalid('constraint or observation budget')
        for obs in entries:
            _keys(obs, {'node', 'lower', 'upper'})
            i = integer(obs['node'], 0, len(forms)-1)
            lo, hi = rational(obs['lower']), rational(obs['upper'])
            # Reversed *observation* intervals are allowed and are inconsistent.
            v, off = forms[i]
            A.extend([[-a for a in v], list(v)])
            b.extend([off-lo, hi-off])
    if len(A) > 128:
        raise Invalid('inequality budget')
    prop = model['assertion']
    _keys(prop, {'node', 'upper'})
    p = integer(prop['node'], 0, len(forms)-1)
    c, off = forms[p]
    q0 = off-rational(prop['upper'])
    # Internal exact arithmetic is also bounded to avoid expression swell.
    for v in [*b, *c, q0, *(x for row in A for x in row)]:
        if max(v.numerator.bit_length(), v.denominator.bit_length()) > 4096:
            raise Invalid('compiled arithmetic exceeds bit budget')
    return bounds, A, b, list(c), q0

def _vec(value, length):
    if type(value) is not list or len(value) != length:
        raise Invalid('vector length')
    return [rational(v) for v in value]

def _witness(value, bounds, A, b):
    if type(value) is not list or len(value) != len(bounds):
        raise Invalid('consistency witness shape')
    z = [integer(v, lo, hi) for v, (lo, hi) in zip(value, bounds)]
    if any(dot(row, z) > rhs for row, rhs in zip(A, b)):
        raise Invalid('consistency witness fails an input or observation constraint')
    return z

def quantum(c, q0):
    # Every affine value lies in delta*Z. A smaller-than-necessary quantum is
    # harmless; the exact subgroup is generated by coefficients and offset.
    vals = [*c, q0]
    den = lcm(*(v.denominator for v in vals))
    num = gcd(*(abs(v.numerator)*(den//v.denominator) for v in vals))
    return F(num, den)

def verify(model: Any, cert: Any) -> str:
    bounds, A, b, c, q0 = compile_model(model)
    if type(cert) is not dict or type(cert.get('kind')) is not str:
        raise Invalid('certificate envelope')
    kind = cert['kind']; m, d = len(A), len(c)
    if kind in ('linear', 'quantized'):
        _keys(cert, {'kind', 'witness', 'multipliers'})
        _witness(cert['witness'], bounds, A, b)
        lam = _vec(cert['multipliers'], m)
        if any(v < 0 for v in lam):
            raise Invalid('negative dual multiplier')
        if any(sum((lam[i]*A[i][j] for i in range(m)), F(0)) != c[j] for j in range(d)):
            raise Invalid('dual identity')
        upper = dot(lam, b)+q0
        if kind == 'linear':
            if upper > 0:
                raise Invalid('bound does not imply the declared assertion')
        else:
            delta = quantum(c, q0)
            if delta == 0 or not upper < delta:
                raise Invalid('strict lattice threshold fails')
        return 'PROVED'
    if kind == 'inconsistent':
        _keys(cert, {'kind', 'multipliers'})
        lam = _vec(cert['multipliers'], m)
        if any(v < 0 for v in lam):
            raise Invalid('negative inconsistency multiplier')
        if any(sum((lam[i]*A[i][j] for i in range(m)), F(0)) != 0 for j in range(d)):
            raise Invalid('inconsistency identity')
        if dot(lam, b) >= 0:
            raise Invalid('strict inconsistency threshold fails')
        return 'INCONSISTENT'
    if kind == 'finite_cover':
        _keys(cert, {'kind', 'decision', 'witness', 'cover'})
        decision = cert['decision']
        if decision not in ('PROVED', 'INCONSISTENT'):
            raise Invalid('cover decision')
        if decision == 'PROVED':
            _witness(cert['witness'], bounds, A, b)
        elif cert['witness'] is not None:
            raise Invalid('inconsistent cover cannot carry a witness')
        count = prod(hi-lo+1 for lo, hi in bounds)
        if type(cert['cover']) is not list or len(cert['cover']) != count:
            raise Invalid('cover is not exhaustive')
        for z, tag in zip(product(*(range(lo, hi+1) for lo, hi in bounds)), cert['cover']):
            if type(tag) is not int:
                raise Invalid('cover entry type')
            if tag == -1:
                if decision != 'PROVED' or dot(c, z)+q0 > 0:
                    raise Invalid('property cover entry is not justified')
            elif 0 <= tag < m:
                if dot(A[tag], z) <= b[tag]:
                    raise Invalid('constraint cover entry is not strictly violated')
            else:
                raise Invalid('cover entry outside row range')
        return decision
    raise Invalid('unsupported proof kind')

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('model'); ap.add_argument('certificate')
    args = ap.parse_args()
    try:
        print(verify(load(args.model), load(args.certificate)))
    except (Invalid, ValueError, OverflowError) as exc:
        raise SystemExit('INVALID_CERTIFICATE: '+str(exc))
