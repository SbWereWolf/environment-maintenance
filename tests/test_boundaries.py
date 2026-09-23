"""Fail-closed input validation and subprocess/public-CLI boundaries."""
import json,os,subprocess,sys
from pathlib import Path
import pytest
from environment_maintenance.catalogue import ContractError,load_catalogue
from environment_maintenance.engine import execute
from environment_maintenance.parameters import resolve
from environment_maintenance.process import run
from test_contract import catalogue,req,params,command
from test_modules import invoke


@pytest.mark.parametrize('kind',[[],{},None])
def test_bad_parameter_type_is_contract_error(kind):
    with pytest.raises(ContractError):resolve({'a':{'type':kind}}, {}, {}, [])


def test_nested_sqlite_sql_cannot_write_during_check(tmp_path):
    sentinel=tmp_path/'outside.sqlite';spec=tmp_path/'schema.json'
    spec.write_text(json.dumps({'version':1,'sql':f"ATTACH DATABASE '{sentinel}' AS outside; CREATE TABLE outside.stolen(id);"}))
    code,_=invoke('sqlite_schema','check',['--path',tmp_path/'missing.sqlite','--schema',spec],tmp_path)
    assert code!=0 and not sentinel.exists()


def test_dependency_catalogue_fails_before_infrastructure_mutation(tmp_path):
    rows=[req('dir','infra'),req('other','deps')];rows[1]['apply']['argv']+=['${missing}']
    c=load_catalogue(catalogue(tmp_path,rows,params(tmp_path)))
    with pytest.raises(ContractError):execute(c,'infra',environ={})
    assert not (tmp_path/'state').exists()


def test_secret_redaction(tmp_path):
    secret='never-in-evidence';p={'token':{'type':'string','secret':True,'default':secret}}
    r={'id':'secret','kind':'infra','check':command('import sys;print(sys.argv[1]);sys.exit(1)'),
       'apply':command('pass'),'recommendation':'value ${token}'}
    r['check']['argv']+=['${token}']
    out=execute(load_catalogue(catalogue(tmp_path,[r],p)),'check',environ={})
    assert secret not in json.dumps(out) and out['parameters']['token']=='[REDACTED]'


def test_duplicate_json_key_rejected(tmp_path):
    p=tmp_path/'cat.json';p.write_text('{"schema":"x","schema":"y"}')
    with pytest.raises(ContractError):load_catalogue(p)


def test_relative_cwd_anchored_to_catalogue(tmp_path):
    sub=tmp_path/'sub';sub.mkdir()
    out=run({'argv':[sys.executable,'-S','-c','import pathlib;print(pathlib.Path.cwd())'],'cwd':'sub','timeout':2},cwd=tmp_path,environ={})
    assert out['status']=='passed' and out['stdout'].strip()==str(sub)


def test_truncation_is_not_pass(tmp_path):
    out=run({'argv':[sys.executable,'-S','-c','print("A"*100)'],'timeout':2,'max_output_bytes':8},cwd=tmp_path,environ={})
    assert out['exit_code']==0 and out['status']=='failed' and not out['capture_complete']


def test_public_cli_unknown_values_exit2_no_side_effect(tmp_path):
    path=catalogue(tmp_path,[req()],params(tmp_path));src=Path(__file__).resolve().parents[1]/'src'
    r=subprocess.run([sys.executable,'-S','-B','-m','environment_maintenance','infra','--catalog',str(path),'--set','not_declared=x'],
       capture_output=True,text=True,env={'PYTHONPATH':str(src)},timeout=10)
    assert r.returncode==2 and json.loads(r.stdout)['status']=='invalid' and not (tmp_path/'state').exists()


def test_repair_wrong_identity_cannot_succeed(tmp_path):
    r={'id':'directory','kind':'infra','check':{'repair':'directory'},'apply':{'repair':'directory'},'recommendation':'Fix plugin'}
    routes=tmp_path/'repairs.json';routes.write_text(json.dumps({'schema':'environment-maintenance/repairs/v1','repairs':{'directory':command('import json;print(json.dumps({"schema":"environment-maintenance/repair-result/v1","requirement_id":"other","mode":"check","status":"satisfied"}))')}}))
    out=execute(load_catalogue(catalogue(tmp_path,[r])),'check',repair_catalog=routes,environ={})
    assert out['exit_code']==3 and out['requirements'][0]['initial_check']['status']=='failed'


def test_all_package_imports_are_independent():
    import ast
    src=Path(__file__).resolve().parents[1]/'src'
    for p in src.rglob('*.py'):
        tree=ast.parse(p.read_text())
        names=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):names.extend(x.name for x in n.names)
            if isinstance(n,ast.ImportFrom):names.append(n.module or '')
        assert not any(n=='poise' or n.startswith('poise.') for n in names),p
