"""Public process-level AAA checks for domain-owned repair modules and routing."""
import hashlib,json,os,sqlite3,subprocess,sys
from pathlib import Path
import pytest
from environment_maintenance.catalogue import ContractError,load_catalogue
from environment_maintenance.engine import execute
from environment_maintenance.repair import RepairRouter
SRC=Path(__file__).resolve().parents[1]/'src'


def invoke(module,mode,args,tmp_path,identity='sample',failure=None):
    request={'schema':'environment-maintenance/repair-request/v1','requirement_id':identity,
             'mode':mode,'parameters':{},'failure':failure}
    result=subprocess.run([sys.executable,'-S','-B','-m','environment_maintenance.repairs.'+module,*map(str,args)],
             input=json.dumps(request),text=True,capture_output=True,cwd=tmp_path,
             env={'PYTHONPATH':str(SRC),'PATH':os.environ['PATH']},timeout=10)
    assert result.stdout, result.stderr
    out=json.loads(result.stdout); assert out['requirement_id']==identity and out['mode']==mode
    return result.returncode,out


def test_directory_missing_check_and_recommend_do_not_create(tmp_path):
    target=tmp_path/'state';args=['--path',target,'--permissions','0750']
    c,r=invoke('directory','check',args,tmp_path);assert c==3 and r['code']=='missing'
    c,r=invoke('directory','recommend',args,tmp_path,failure={'result':{'response':r}})
    assert c==0 and r['recommendation'] and not target.exists()


def test_directory_create_and_idempotence(tmp_path):
    target=tmp_path/'state';args=['--path',target,'--permissions','0750']
    c,r=invoke('directory','apply',args,tmp_path);assert c==0 and target.stat().st_mode&0o777==0o750
    inode=target.stat().st_ino
    assert invoke('directory','check',args,tmp_path)[0]==0
    assert invoke('directory','apply',args,tmp_path)[1]['status']=='satisfied'
    assert target.stat().st_ino==inode


def test_directory_existing_wrong_mode_not_rewritten(tmp_path):
    target=tmp_path/'state';target.mkdir(mode=0o555)
    code,_=invoke('directory','apply',['--path',target,'--permissions','0750'],tmp_path)
    assert code!=0 and target.stat().st_mode&0o777==0o555


@pytest.mark.parametrize('module',['directory','json_config','sqlite_schema'])
def test_symlink_parent_refused(tmp_path,module):
    outside=tmp_path/'outside';outside.mkdir();(tmp_path/'link').symlink_to(outside,target_is_directory=True)
    args=['--path',tmp_path/'link'/'target']
    if module=='directory':args+=['--permissions','0750']
    elif module=='json_config':
        template=tmp_path/'template.json';template.write_text('{}');args+=['--template',template]
    else:
        spec=tmp_path/'schema.json';spec.write_text(json.dumps({'version':1,'sql':'CREATE TABLE items(id INTEGER PRIMARY KEY);'}));args+=['--schema',spec]
    assert invoke(module,'apply',args,tmp_path)[0]!=0
    assert list(outside.iterdir())==[]


def test_json_create_and_preserve_user_configuration(tmp_path):
    template=tmp_path/'template.json';template.write_text('{"project":"example"}')
    target=tmp_path/'config.json';args=['--path',target,'--template',template,'--required','project']
    assert invoke('json_config','apply',args,tmp_path)[0]==0
    target.write_text('{"project":"changed","custom":true}')
    before=target.read_bytes();assert invoke('json_config','apply',args,tmp_path)[0]==0;assert target.read_bytes()==before


def test_json_corrupt_preserved_with_advice(tmp_path):
    template=tmp_path/'template.json';template.write_text('{"project":"x"}')
    target=tmp_path/'config.json';target.write_text('broken{');args=['--path',target,'--template',template,'--required','project']
    c,r=invoke('json_config','apply',args,tmp_path);assert c!=0 and target.read_text()=='broken{'
    c,r=invoke('json_config','recommend',args,tmp_path,failure={'result':{'response':r}})
    assert c==0 and 'JSON' in r['recommendation']


def test_json_template_invalid_no_target(tmp_path):
    template=tmp_path/'template.json';template.write_text('{}');target=tmp_path/'config.json'
    assert invoke('json_config','apply',['--path',target,'--template',template,'--required','project'],tmp_path)[0]!=0
    assert not target.exists()


def schema(tmp_path):
    s=tmp_path/'schema.json';s.write_text(json.dumps({'version':7,'sql':'CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT NOT NULL);'}));return s


def test_sqlite_create_schema_and_preserve_data(tmp_path):
    target=tmp_path/'state.sqlite';args=['--path',target,'--schema',schema(tmp_path)]
    assert invoke('sqlite_schema','apply',args,tmp_path)[0]==0
    with sqlite3.connect(target) as c:c.execute('insert into items values(1,?)',('retained',))
    before=target.read_bytes();assert invoke('sqlite_schema','check',args,tmp_path)[0]==0
    assert invoke('sqlite_schema','apply',args,tmp_path)[0]==0 and target.read_bytes()==before


@pytest.mark.parametrize('corrupt',['bytes','version','schema'])
def test_sqlite_incompatible_never_rebuilt(tmp_path,corrupt):
    target=tmp_path/'state.sqlite';args=['--path',target,'--schema',schema(tmp_path)]
    if corrupt=='bytes':target.write_bytes(b'corrupt database, preserve me')
    else:
        with sqlite3.connect(target) as c:
            c.execute('CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT NOT NULL)' if corrupt=='version' else 'CREATE TABLE other(id)')
            c.execute('PRAGMA user_version='+('6' if corrupt=='version' else '7'))
    before=target.read_bytes();code,r=invoke('sqlite_schema','apply',args,tmp_path);assert code!=0
    assert target.read_bytes()==before
    assert invoke('sqlite_schema','recommend',args,tmp_path,failure={'result':{'response':r}})[0]==0


def test_sqlite_bad_schema_no_partial_db(tmp_path):
    s=tmp_path/'schema.json';s.write_text('{"version":1,"sql":"WRONG SQL"}')
    target=tmp_path/'state.sqlite';assert invoke('sqlite_schema','apply',['--path',target,'--schema',s],tmp_path)[0]!=0
    assert not target.exists()


def test_real_router_all_three_modes(tmp_path):
    path=tmp_path/'state';routing=tmp_path/'repairs.json'
    routing.write_text(json.dumps({'schema':'environment-maintenance/repairs/v1','repairs':{'dir':
        {'argv':[sys.executable,'-S','-B','-m','environment_maintenance.repairs.directory','--path','${path}','--permissions','0750'],
         'timeout':5,'env':{'PYTHONPATH':str(SRC)}}}}))
    cat=tmp_path/'catalog.json';cat.write_text(json.dumps({'schema':'environment-maintenance/requirements/v1',
        'parameters':{'path':{'type':'string','default':str(path)}},'requirements':[
        {'id':'dir','kind':'infra','check':{'repair':'dir'},'apply':{'repair':'dir'},'recommendation':{'repair':'dir'}}]}))
    c=load_catalogue(cat);dry=execute(c,'infra',repair_catalog=routing,dry_run=True,environ={})
    assert dry['requirements'][0]['recommendation_result']['response']['mode']=='recommend' and not path.exists()
    assert execute(c,'infra',repair_catalog=routing,environ={})['status']=='repaired'
    assert execute(c,'check',repair_catalog=routing,environ={})['status']=='ready'


def test_missing_route_rejected_before_any_action(tmp_path):
    cat=tmp_path/'catalog.json';cat.write_text(json.dumps({'schema':'environment-maintenance/requirements/v1','parameters':{},'requirements':[
      {'id':'missing','kind':'infra','check':{'repair':'missing'},'apply':{'repair':'missing'},'recommendation':'help'}]}))
    routes=tmp_path/'repairs.json';routes.write_text('{"schema":"environment-maintenance/repairs/v1","repairs":{}}')
    with pytest.raises(ContractError):execute(load_catalogue(cat),'infra',repair_catalog=routes)


def test_python_runtime_selected_interpreter(tmp_path):
    args=['--minimum','3.11','--maximum','4']
    assert invoke('python_runtime','check',args,tmp_path)[0]==0
    assert invoke('python_runtime','apply',args,tmp_path)[1]['status']=='satisfied'


def test_python_runtime_not_reinstalled_on_mismatch(tmp_path):
    args=['--minimum','99','--maximum','100'];code,r=invoke('python_runtime','apply',args,tmp_path)
    assert code==3 and r['code']=='version'
    code,r=invoke('python_runtime','recommend',args,tmp_path,failure={'result':{'response':r}})
    assert code==0 and 'python' in r['recommendation'] and list(tmp_path.iterdir())==[]
