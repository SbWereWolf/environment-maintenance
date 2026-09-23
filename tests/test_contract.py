"""Public contract, written before implementing the requirements application."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from environment_maintenance.catalogue import load_catalogue, ContractError
from environment_maintenance.parameters import resolve, expand
from environment_maintenance.engine import execute
from environment_maintenance.process import run


def command(script):
    return {'argv': [sys.executable, '-S', '-c', script], 'timeout': 3}


def catalogue(tmp_path, requirements=None, params=None):
    raw={'schema':'environment-maintenance/requirements/v1',
         'parameters':params or {}, 'requirements':requirements or []}
    path=tmp_path/'requirements.json'; path.write_text(json.dumps(raw)); return path


def req(identifier='folder', kind='infra'):
    return {'id':identifier,'kind':kind,
            'check':command("import pathlib,sys;sys.exit(not pathlib.Path('${path}').is_dir())"),
            'apply':command("import pathlib;pathlib.Path('${path}').mkdir()"),
            'recommendation':'Создайте каталог ${path}.'}


def params(tmp_path):
    return {'path':{'type':'string','default':str(tmp_path/'state')}}


@pytest.mark.parametrize('field',['check','apply','kind','recommendation','id'])
def test_all_requirement_fields_mandatory(tmp_path,field):
    r=req(); del r[field]
    with pytest.raises(ContractError): load_catalogue(catalogue(tmp_path,[r],params(tmp_path)))


@pytest.mark.parametrize('kind',['dependency','',None,123])
def test_kind_explicit(tmp_path,kind):
    with pytest.raises(ContractError): load_catalogue(catalogue(tmp_path,[req(kind=kind)],params(tmp_path)))


def test_duplicate_rejected(tmp_path):
    with pytest.raises(ContractError): load_catalogue(catalogue(tmp_path,[req(),req()],params(tmp_path)))


def test_unknown_parameter_fails_before_any_command(tmp_path):
    r=req(); r['apply']=command("import pathlib;pathlib.Path('${missing}').mkdir()")
    c=load_catalogue(catalogue(tmp_path,[r],params(tmp_path)))
    with pytest.raises(ContractError): execute(c,'infra',environ={})
    assert not (tmp_path/'state').exists()


def test_override_and_origin():
    spec={'root':{'type':'string','default':'default','env':'MY_ROOT'}}
    value,origin=resolve(spec,{'root':'config'},{'MY_ROOT':'environment'},['root=cli'])
    assert value=={'root':'cli'} and origin=={'root':'cli'}


def test_environment_not_implicit():
    v,_=resolve({'root':{'type':'string','default':'default'}},{},{'root':'evil'},[])
    assert v['root']=='default'


@pytest.mark.parametrize('value',[True,1,{},[],None])
def test_typed_parameter_rejects_wrong_type(value):
    with pytest.raises(ContractError): resolve({'x':{'type':'string'}},{'x':value},{},[])


def test_boolean_and_integer_cli():
    v,_=resolve({'n':{'type':'integer'},'b':{'type':'boolean'}},{},{},['n=2','b=false'])
    assert v=={'n':2,'b':False}


def test_unknown_override():
    with pytest.raises(ContractError): resolve({}, {}, {}, ['unknown=1'])


def test_expansion_no_reinterpretation():
    assert expand(['echo','${path}'],{'path':'${evil}; $(rm -f x)'})==['echo','${evil}; $(rm -f x)']


def test_missing_expansion():
    with pytest.raises(ContractError): expand(['${no}'],{})


@pytest.mark.parametrize('operation',['infra','deps'])
def test_symmetric_repair_and_idempotence(tmp_path,operation):
    c=load_catalogue(catalogue(tmp_path,[req(kind=operation)],params(tmp_path)))
    first=execute(c,operation,environ={})
    assert first['status']=='repaired' and first['exit_code']==0
    assert first['requirements'][0]['final_check']['exit_code']==0
    again=execute(c,operation,environ={})
    assert again['status']=='ready' and 'apply' not in again['requirements'][0]


@pytest.mark.parametrize('operation',['infra','deps','check'])
def test_check_and_dry_run_no_apply(tmp_path,operation):
    c=load_catalogue(catalogue(tmp_path,[req(kind='deps' if operation=='deps' else 'infra')],params(tmp_path)))
    out=execute(c,operation,dry_run=operation!='check',environ={})
    assert out['status']=='action_required' and out['exit_code']==3
    assert not (tmp_path/'state').exists()
    assert 'apply' not in out['requirements'][0]
    assert out['requirements'][0]['recommendation'].startswith('Создайте')


def test_check_both_kinds(tmp_path):
    c=load_catalogue(catalogue(tmp_path,[req('a','infra'),req('b','deps')],params(tmp_path)))
    out=execute(c,'check',environ={}); assert len(out['requirements'])==2


def test_kind_filter(tmp_path):
    c=load_catalogue(catalogue(tmp_path,[req('a','infra'),req('b','deps')],params(tmp_path)))
    assert [r['id'] for r in execute(c,'deps',environ={})['requirements']]==['b']


def test_failed_apply_not_success(tmp_path):
    r=req();r['apply']=command('raise SystemExit(8)')
    c=load_catalogue(catalogue(tmp_path,[r],params(tmp_path)))
    out=execute(c,'infra',environ={})
    assert out['status']=='failed' and out['exit_code']==4
    assert out['requirements'][0]['apply']['exit_code']==8
    assert out['requirements'][0]['final_check']['exit_code']!=0


def test_successful_apply_must_be_rechecked(tmp_path):
    r=req();r['apply']=command('pass')
    out=execute(load_catalogue(catalogue(tmp_path,[r],params(tmp_path))),'infra',environ={})
    assert out['status']=='failed' and out['exit_code']==4


def test_empty_deps_not_required(tmp_path):
    out=execute(load_catalogue(catalogue(tmp_path)),'deps',environ={})
    assert out['status']=='not_required' and out['exit_code']==0


def test_executable_not_found_reported(tmp_path):
    out=run({'argv':['/nonexistent/prog'],'timeout':1},cwd=tmp_path,environ={})
    assert out['exit_code']!=0 and out['status']=='failed'


def test_timeout_reported(tmp_path):
    out=run({'argv':[sys.executable,'-S','-c','import time;time.sleep(4)'],'timeout':0.1},cwd=tmp_path,environ={})
    assert out['timed_out'] and out['status']=='failed'


def test_no_shell_injection(tmp_path):
    x='; touch '+str(tmp_path/'pwned')
    out=run({'argv':[sys.executable,'-S','-c','import sys;print(sys.argv[1])',x],'timeout':2},cwd=tmp_path,environ={})
    assert out['stdout'].strip()==x and not (tmp_path/'pwned').exists()


def test_inherit_environment_is_explicit(tmp_path):
    out=run({'argv':[sys.executable,'-S','-c','import os;print(os.getenv("SECRET_UNDECLARED", "absent"))'],'timeout':2},cwd=tmp_path,environ={})
    assert out['stdout'].strip()=='absent'


def test_config_command_type_not_shell(tmp_path):
    r=req();r['check']={'command':'echo pass'}
    with pytest.raises(ContractError):load_catalogue(catalogue(tmp_path,[r],params(tmp_path)))
