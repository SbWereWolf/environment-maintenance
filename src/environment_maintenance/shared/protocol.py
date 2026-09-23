"""Shared wire protocol and diagnostics. No domain-specific repairs."""
import json
import sys

class RepairError(Exception):
    def __init__(self,code,detail):super().__init__(detail);self.code=code


def result(status,code,**extra):return {'status':status,'code':code,**extra}


def serve(parser,handler):
    args=parser.parse_args()
    try:
        body=sys.stdin.read(1048577)
        if len(body)>1048576:raise ValueError('Input too large')
        r=json.loads(body)
        if not isinstance(r,dict) or r.get('schema')!='environment-maintenance/repair-request/v1' or r.get('mode') not in ('check','apply','recommend') or not isinstance(r.get('requirement_id'),str) or not r['requirement_id']:
            raise ValueError('Invalid request')
    except (ValueError,TypeError) as exc:
        print(json.dumps({'status':'failed','code':'invalid_request','detail':str(exc)}));return 2
    try:out=handler(args,r)
    except RepairError as exc:out=result('action_required',exc.code,detail=str(exc))
    except (OSError,ValueError) as exc:out=result('failed','operation_error',detail=str(exc))
    out.update(schema='environment-maintenance/repair-result/v1',requirement_id=r['requirement_id'],mode=r['mode'])
    print(json.dumps(out,ensure_ascii=False))
    return 0 if out['status'] in ('satisfied','repaired','recommended') else 3 if out['status']=='action_required' else 4


def recommend(request,templates,context):
    failure=request.get('failure') or {}
    code=failure.get('result',{}).get('response',{}).get('code','unknown')
    return result('recommended',code,recommendation=templates.get(code,templates['unknown']).format_map(context))
