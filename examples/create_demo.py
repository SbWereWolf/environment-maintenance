"""Create an explicit disposable profile. Never use it as a Poise production config."""
import argparse,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('destination',type=Path);a=p.parse_args()
r=a.destination.resolve();r.mkdir(parents=True,exist_ok=False)
source=Path(__file__).resolve().parents[1]/'src'
(r/'config-template.json').write_text('{"application":"maintenance-demo"}\n')
(r/'schema.json').write_text(json.dumps({'version':1,'sql':'CREATE TABLE items(id INTEGER PRIMARY KEY, value TEXT NOT NULL);'}))
spec={'python':{'type':'string','default':sys.executable},'modules':{'type':'string','default':str(source)},'workspace':{'type':'string','default':str(r)},'runtime':{'type':'string','default':str(r/'runtime')}}
items=[];routes={}
for key,kind,module,args in [
 ('python-runtime','deps','python_runtime',['--minimum','3.11','--maximum','4']),
 ('state-directory','infra','directory',['--path','${runtime}','--permissions','0750']),
 ('app-config','infra','json_config',['--path','${runtime}/config.json','--template','${workspace}/config-template.json','--required','application']),
 ('app-db','infra','sqlite_schema',['--path','${runtime}/state.sqlite','--schema','${workspace}/schema.json'])]:
 items.append({'id':key,'kind':kind,'check':{'repair':key},'apply':{'repair':key},'recommendation':{'repair':key}})
 routes[key]={'argv':['${python}','-B','-m','environment_maintenance.repairs.'+module,*args],'timeout':15,'env':{'PYTHONPATH':'${modules}','PYTHONDONTWRITEBYTECODE':'1'}}
(r/'requirements.json').write_text(json.dumps({'schema':'environment-maintenance/requirements/v1','parameters':spec,'requirements':items},indent=2))
(r/'repairs.json').write_text(json.dumps({'schema':'environment-maintenance/repairs/v1','repairs':routes},indent=2))
print(r)
