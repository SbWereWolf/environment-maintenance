"""Validated declarative requirements. Product prerequisites never live in this module."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

class ContractError(ValueError):
    """The complete input must be rejected before executing any command."""

@dataclass(frozen=True)
class Catalogue:
    path: Path
    data: dict[str, Any]


def read_json(path: Path) -> dict:
    def unique_pairs(pairs):
        out={}
        for key,value in pairs:
            if key in out: raise ContractError(f'Duplicate JSON key: {key}')
            out[key]=value
        return out
    try:
        value=json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique_pairs)
    except (OSError, ValueError) as exc:
        raise ContractError(f'Cannot read {path}: {exc}') from exc
    if not isinstance(value,dict): raise ContractError(f'Expected object: {path}')
    return value


def validate_action(action: Any, requirement_id: str) -> None:
    if not isinstance(action,dict): raise ContractError(f'{requirement_id}: action must be object')
    if 'repair' in action:
        if set(action)!={'repair'} or action['repair']!=requirement_id:
            raise ContractError(f'{requirement_id}: repair route must match requirement id')
        return
    if set(action)-{'argv','timeout','env','cwd','max_output_bytes'}:
        raise ContractError(f'{requirement_id}: unsupported command fields')
    argv=action.get('argv'); timeout=action.get('timeout')
    if not isinstance(argv,list) or not argv or not all(isinstance(x,str) and '\0' not in x for x in argv) or not argv[0]:
        raise ContractError(f'{requirement_id}: nonempty string argv is required')
    if type(timeout) not in (int,float) or not 0 < timeout <= 3600:
        raise ContractError(f'{requirement_id}: timeout must be 0..3600 seconds')
    env=action.get('env',{})
    if not isinstance(env,dict) or not all(isinstance(k,str) and k and '=' not in k and '\0' not in k and isinstance(v,str) and '\0' not in v for k,v in env.items()):
        raise ContractError(f'{requirement_id}: invalid env')
    if 'cwd' in action and (not isinstance(action['cwd'],str) or '\0' in action['cwd']):
        raise ContractError(f'{requirement_id}: invalid cwd')
    if 'max_output_bytes' in action and (type(action['max_output_bytes']) is not int or not 1<=action['max_output_bytes']<=16777216):
        raise ContractError(f'{requirement_id}: invalid output limit')


def load_catalogue(path: str | Path) -> Catalogue:
    path=Path(path).resolve(); raw=read_json(path)
    if raw.get('schema')!='environment-maintenance/requirements/v1':
        raise ContractError('Unsupported requirements schema')
    if set(raw)-{'schema','parameters','requirements','inherit_env'}:
        raise ContractError('Unsupported catalogue fields')
    if not isinstance(raw.get('parameters'),dict) or not isinstance(raw.get('requirements'),list):
        raise ContractError('parameters object and requirements array are required')
    seen=set()
    for r in raw['requirements']:
        if not isinstance(r,dict) or not {'id','kind','check','apply','recommendation'}<=r.keys():
            raise ContractError('Requirement needs id, kind, check, apply, recommendation')
        if set(r)-{'id','kind','check','apply','recommendation','description'}:
            raise ContractError('Unsupported requirement fields')
        name=r['id']
        if not isinstance(name,str) or not name or name in seen: raise ContractError('Invalid/duplicate requirement id')
        seen.add(name)
        if r['kind'] not in ('infra','deps'): raise ContractError(f'{name}: kind must be infra or deps')
        validate_action(r['check'],name);validate_action(r['apply'],name)
        if not isinstance(r['recommendation'],str): validate_action(r['recommendation'],name)
        elif not r['recommendation'].strip(): raise ContractError(f'{name}: empty recommendation')
        # Nontrivial recommendations must come from the SAME domain repair module.
        if isinstance(r['recommendation'],dict) and set(r['recommendation'])!={'repair'}:
            raise ContractError(f'{name}: recommendation must be text or its own repair tool')
    inherited=raw.get('inherit_env',[])
    if not isinstance(inherited,list) or not all(isinstance(x,str) and x and '=' not in x and '\0' not in x for x in inherited):
        raise ContractError('inherit_env must be an explicit list of names')
    return Catalogue(path,raw)
