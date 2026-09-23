"""Typed, one-pass parameter expansion; never evaluate shell syntax."""
import json
import re
from .catalogue import ContractError
TOKEN=re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_.-]*)\}')
TYPES={'string':str,'integer':int,'boolean':bool,'number':(int,float)}


def resolve(spec, values=None, environ=None, overrides=None):
    values=values or {}; environ=environ or {}; overrides=overrides or []
    if set(values)-set(spec): raise ContractError('Unknown values: '+','.join(sorted(set(values)-set(spec))))
    effective={}; provenance={}
    for k,s in spec.items():
        if not isinstance(k,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*',k) or not isinstance(s,dict):
            raise ContractError('Invalid parameter declaration')
        if set(s)-{'type','default','env','secret','description'} or s.get('type') not in TYPES:
            raise ContractError(f'{k}: explicit known type required')
        if 'env' in s and not isinstance(s['env'],str):raise ContractError(f'{k}: env must be string')
        if 'secret' in s and type(s['secret']) is not bool:raise ContractError(f'{k}: secret must be boolean')
        if 'default' in s: effective[k]=s['default'];provenance[k]='default'
        if k in values: effective[k]=values[k];provenance[k]='values'
        if s.get('env') in environ:
            effective[k]=_parse(environ[s['env']],s['type'],k);provenance[k]='environment'
    for pair in overrides:
        if '=' not in pair:raise ContractError('Override must be name=value')
        k,v=pair.split('=',1)
        if k not in spec:raise ContractError(f'Unknown override: {k}')
        effective[k]=_parse(v,spec[k]['type'],k);provenance[k]='cli'
    for k,s in spec.items():
        if k not in effective:raise ContractError(f'Missing parameter: {k}')
        t=TYPES[s['type']];v=effective[k]
        if not isinstance(v,t) or (isinstance(v,bool) and s['type']!='boolean'):
            raise ContractError(f'{k}: expected {s["type"]}')
        if isinstance(v,str) and '\0' in v: raise ContractError(f'{k}: NUL is forbidden')
        if isinstance(v,float):
            import math
            if not math.isfinite(v):raise ContractError(f'{k}: finite number required')
    return effective,provenance


def _parse(value,kind,name):
    if kind=='string':return value
    try:return json.loads(value)
    except (ValueError,TypeError) as e:raise ContractError(f'{name}: invalid typed value') from e


def expand(value,params):
    if isinstance(value,str):
        def replace(m):
            key=m.group(1)
            if key not in params:raise ContractError(f'Unknown placeholder: {key}')
            v=params[key]
            return json.dumps(v) if isinstance(v,(bool,int,float)) else v
        return TOKEN.sub(replace,value)
    if isinstance(value,list):return [expand(v,params) for v in value]
    if isinstance(value,dict):return {k:expand(v,params) for k,v in value.items()}
    return value


def redact(value, secrets):
    if isinstance(value,str):
        for s in sorted((str(s) for s in secrets if str(s)),key=len,reverse=True):value=value.replace(s,'[REDACTED]')
        return value
    if isinstance(value,list):return [redact(v,secrets) for v in value]
    if isinstance(value,dict):return {k:redact(v,secrets) for k,v in value.items()}
    return value
