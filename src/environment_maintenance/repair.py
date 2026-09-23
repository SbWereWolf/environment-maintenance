"""Exact requirement-id routing; domain expertise is owned by the selected executable."""
import argparse
import json
from pathlib import Path
import sys
from .catalogue import ContractError, read_json, validate_action
from .parameters import expand
from .process import run

class RepairRouter:
    def __init__(self, path, params):
        self.path=Path(path).resolve();self.raw=read_json(self.path)
        if set(self.raw)!={'schema','repairs'} or self.raw['schema']!='environment-maintenance/repairs/v1' or not isinstance(self.raw['repairs'],dict):
            raise ContractError('Unsupported repair catalogue')
        self.commands={}
        for key,action in self.raw['repairs'].items():
            validate_action(action,key)
            if 'repair' in action:raise ContractError('Recursive repair routing is forbidden')
            resolved=expand(action,params)
            validate_action(resolved,key)
            self.commands[key]=resolved
    def require(self,key):
        if key not in self.commands:raise ContractError(f'Missing repair route: {key}')
    def invoke(self, key, mode, params, failure, environ):
        self.require(key)
        request={'schema':'environment-maintenance/repair-request/v1','requirement_id':key,
                 'mode':mode,'parameters':params,'failure':failure}
        result=run(self.commands[key],cwd=self.path.parent,environ=environ,request=json.dumps(request))
        if result['capture_complete'] and result['stdout']:
            try:
                response=json.loads(result['stdout'])
                if not isinstance(response,dict) or response.get('schema')!='environment-maintenance/repair-result/v1' or response.get('requirement_id')!=key or response.get('mode')!=mode:
                    raise ValueError('Unbound/invalid repair response')
                if response.get('status') not in ('satisfied','repaired','action_required','failed','recommended'):
                    raise ValueError('Invalid repair status')
                expected=('satisfied',) if mode=='check' else ('satisfied','repaired') if mode=='apply' else ('recommended',)
                if result['status']=='passed' and response['status'] not in expected:
                    raise ValueError('Exit 0 contradicts domain status')
                result['response']=response
            except (ValueError,TypeError) as exc:
                result['status']='failed';result['error']=str(exc)
        else:
            result['status']='failed';result['error']=result['error'] or 'No complete repair response'
        return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='Dispatch one requirement to its own repair module')
    parser.add_argument('requirement_id');parser.add_argument('--mode',required=True,choices=['check','apply','recommend'])
    parser.add_argument('--catalog',type=Path,required=True);parser.add_argument('--input',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        request=read_json(args.input);params=request.get('parameters',{})
        result=RepairRouter(args.catalog,params).invoke(args.requirement_id,args.mode,params,request.get('failure'),{})
        print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='passed' else 4
    except ContractError as e:print(json.dumps({'status':'invalid','error':str(e)}));return 2

if __name__=='__main__':raise SystemExit(main())
