#!/usr/bin/env python3
"""Reproduction entry point with mandatory research-record validation."""
from pathlib import Path
import subprocess, sys
HERE=Path(__file__).resolve().parent
rc=subprocess.run([sys.executable,str(HERE/'reproduce_core.py'),*sys.argv[1:]],cwd=HERE).returncode
if rc:
    raise SystemExit(rc)
stage=None
for i,a in enumerate(sys.argv[1:]):
    if a=='--stage' and i+2<=len(sys.argv[1:]):
        stage=sys.argv[1:][i+1]
    elif a.startswith('--stage='):
        stage=a.split('=',1)[1]
if stage in (None,'all','validation'):
    subprocess.run([sys.executable,str(HERE/'tools'/'verify_research_records.py')],cwd=HERE,check=True)
    subprocess.run([sys.executable,str(HERE/'tools'/'final_code_audit.py')],cwd=HERE,check=True)
