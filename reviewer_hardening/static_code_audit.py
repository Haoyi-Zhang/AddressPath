#!/usr/bin/env python3
from __future__ import annotations
import ast,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent; A=HERE.parent
records=[]; forbidden=[]
for p in sorted(A.rglob('*.py')):
    if any(x in p.parts for x in ('reproduction','full-reproduction','__pycache__')): continue
    text=p.read_text(encoding='utf-8',errors='strict')
    tree=ast.parse(text,filename=str(p))
    imports=[]; calls=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import): imports += [a.name for a in n.names]
        elif isinstance(n,ast.ImportFrom): imports.append(n.module or '')
        elif isinstance(n,ast.Call):
            name=''
            if isinstance(n.func,ast.Name): name=n.func.id
            elif isinstance(n.func,ast.Attribute): name=n.func.attr
            calls.append(name)
            if name in {'eval','exec'}: forbidden.append(f'{p}: {name}')
            for kw in n.keywords:
                if kw.arg=='shell' and isinstance(kw.value,ast.Constant) and kw.value.value is True:
                    forbidden.append(f'{p}: subprocess shell=True')
    if any(i.split('.')[0] in {'pickle','marshal','dill'} for i in imports): forbidden.append(f'{p}: unsafe serialization import')
    records.append({'path':str(p.relative_to(A)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'imports':sorted(set(imports))})
if forbidden: raise AssertionError(forbidden)
out={'schema':'static-code-audit-v1','status':'PASS','python_files':len(records),'total_bytes':sum(r['bytes'] for r in records),'forbidden_constructs':forbidden,'files':records}
(HERE/'static_code_audit.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps({'status':'PASS','python_files':len(records)},sort_keys=True))
