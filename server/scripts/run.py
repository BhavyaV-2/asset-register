"""Run a supported project command with local environment settings."""
from pathlib import Path
import os,runpy,sys
from urllib.parse import urlsplit,urlunsplit
folder=Path(__file__).resolve().parents[1]
settings=folder/'.env'
if settings.exists():
    for line in settings.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key,value=line.split('=',1)
            os.environ.setdefault(key.strip(),value.strip())
sys.path.insert(0,str(folder))
if len(sys.argv)<2:raise SystemExit('Choose start_server, load_demo_state, make_test_data, time_the_map or test.')
command=sys.argv.pop(1)
if command in ['test','make_test_data','time_the_map']:
    address=urlsplit(os.environ['DATABASE_URL'])
    name='asset_register_test' if command=='test' else 'asset_register_load'
    os.environ['DATABASE_URL']=urlunsplit(address._replace(path='/'+name))
if command=='test':
    import pytest
    raise SystemExit(pytest.main([str(folder/'tests'),'-q']+sys.argv[1:]))
if command not in ['start_server','load_demo_state','make_test_data','time_the_map']:raise SystemExit('Choose a supported command.')
runpy.run_module('scripts.'+command,run_name='__main__')
