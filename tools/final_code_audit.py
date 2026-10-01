#!/usr/bin/env python3
"""Static and serialization audit for the standalone research artifact."""
from __future__ import annotations
from pathlib import Path
import ast, csv, json, os, re, sys, zipfile
ROOT=Path(__file__).resolve().parents[1]
EXCLUDE_PARTS={'reproduction','final-validation','.git','__pycache__'}

def excluded(p): return any(x in EXCLUDE_PARTS for x in p.parts)
def strict_json(path):
    def hook(pairs):
        out={}; seen=set()
        for k,v in pairs:
            if k in seen: raise ValueError(f'duplicate key {k!r}')
            seen.add(k); out[k]=v
        return out
    with path.open(encoding='utf-8') as f: return json.load(f,object_pairs_hook=hook)
def main():
    errors=[]; pyfiles=[]; jsonfiles=[]; csvfiles=[]; total=0
    for p in ROOT.rglob('*'):
        rel=p.relative_to(ROOT)
        if excluded(rel): continue
        if p.is_symlink(): errors.append(f'symbolic link is not allowed: {rel}'); continue
        if p.is_dir(): continue
        total+=p.stat().st_size
        if p.suffix in {'.pyc','.pyo'} or p.name=='.DS_Store': errors.append(f'generated/cache file present: {rel}')
        if p.suffix.lower() in {'.zip','.tar','.gz','.tgz','.7z'}: errors.append(f'nested archive present: {rel}')
        if p.suffix=='.py': pyfiles.append(p)
        elif p.suffix=='.json': jsonfiles.append(p)
        elif p.suffix=='.csv': csvfiles.append(p)
    if total>128*1024*1024: errors.append(f'artifact exceeds 128 MiB: {total} bytes')
    network_roots={'requests','socket','http','urllib','ftplib','paramiko'}
    for p in pyfiles:
        rel=p.relative_to(ROOT)
        try: src=p.read_text(encoding='utf-8'); tree=ast.parse(src,filename=str(rel))
        except Exception as e: errors.append(f'{rel}: parse/UTF-8 failure: {e}'); continue
        if rel != Path('tools/final_code_audit.py') and re.search(r'\b(?:TODO|TBD|FIXME|XXX)\b',src,re.I): errors.append(f'{rel}: unfinished marker')
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names=[]
                if isinstance(node,ast.Import): names=[a.name.split('.')[0] for a in node.names]
                elif node.module: names=[node.module.split('.')[0]]
                if any(n in network_roots for n in names): errors.append(f'{rel}:{node.lineno}: network-capable import {names}')
            if isinstance(node,ast.Call):
                name=''
                if isinstance(node.func,ast.Name): name=node.func.id
                elif isinstance(node.func,ast.Attribute): name=node.func.attr
                if name in {'eval','exec'}: errors.append(f'{rel}:{node.lineno}: dynamic execution via {name}')
                for kw in node.keywords:
                    if kw.arg=='shell' and isinstance(kw.value,ast.Constant) and kw.value.value is True: errors.append(f'{rel}:{node.lineno}: subprocess shell=True')
            if isinstance(node,ast.Raise) and isinstance(node.exc,ast.Call) and isinstance(node.exc.func,ast.Name) and node.exc.func.id=='NotImplementedError':
                errors.append(f'{rel}:{node.lineno}: NotImplementedError')
    for p in jsonfiles:
        try: strict_json(p)
        except Exception as e: errors.append(f'{p.relative_to(ROOT)}: invalid/non-unique JSON: {e}')
    for p in csvfiles:
        try:
            with p.open(newline='',encoding='utf-8-sig') as f:
                r=csv.reader(f); rows=list(r)
            if not rows: errors.append(f'{p.relative_to(ROOT)}: empty CSV')
            elif len({len(x) for x in rows})!=1: errors.append(f'{p.relative_to(ROOT)}: ragged CSV')
        except Exception as e: errors.append(f'{p.relative_to(ROOT)}: CSV parse failure: {e}')
    # Entrypoints and documentation are mandatory.
    for name in ('reproduce.py','README.md'):
        if not (ROOT/name).is_file(): errors.append(f'missing required root file {name}')
    # Verify all Python sources compile without creating cache files in the tree.
    for p in pyfiles:
        try: compile(p.read_text(encoding='utf-8'),str(p.relative_to(ROOT)),'exec',dont_inherit=True)
        except Exception as e: errors.append(f'{p.relative_to(ROOT)}: compile failure: {e}')
    if errors: raise SystemExit('CODE AUDIT FAILED\n- '+'\n- '.join(sorted(set(errors))))
    print(json.dumps({'status':'PASS','python_files':len(pyfiles),'json_files':len(jsonfiles),'csv_files':len(csvfiles),'artifact_bytes':total,'network_imports':0,'dynamic_execution_calls':0,'duplicate_json_keys':0},sort_keys=True))
if __name__=='__main__': main()
