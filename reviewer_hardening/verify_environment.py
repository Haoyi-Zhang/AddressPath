#!/usr/bin/env python3
import json,sys,platform
from pathlib import Path
p=Path(__file__).with_name('validation_environment.json'); d=json.loads(p.read_text())
assert d['schema']=='validation-environment-v1'
major=int(sys.version_info.major); minor=int(sys.version_info.minor)
assert major==3 and minor>=10, 'Python 3.10+ required for the reviewer-hardening utilities'
print(json.dumps({'status':'PASS','current_python':platform.python_version(),'frozen_python':d['python'].split()[0],'note':'Exact timing is not a portability requirement'},sort_keys=True))
