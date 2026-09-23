"""One executor for both environment categories; commands carry domain knowledge."""
import json
import os
from .catalogue import ContractError,validate_action
from .parameters import expand,resolve,redact
from .process import run
from .repair import RepairRouter


def execute(catalogue, operation, *, values=None, overrides=None, environ=None, dry_run=False, repair_catalog=None):
    if operation not in ('infra','deps','check'):raise ContractError('Unknown operation')
    raw=catalogue.data; host=dict(os.environ if environ is None else environ)
    params,origins=resolve(raw['parameters'],values,host,overrides)
    secrets=[params[k] for k,s in raw['parameters'].items() if s.get('secret')]
    env={k:host[k] for k in raw.get('inherit_env',[]) if k in host}
    # Validate the ENTIRE catalogue and every route before any side effects.
    items=expand(raw['requirements'],params)
    router=RepairRouter(repair_catalog,params) if repair_catalog else None
    for item in items:
        for field in ('check','apply','recommendation'):
            action=item[field]
            if isinstance(action,str):continue
            validate_action(action,item['id'])
            if 'repair' in action:
                if router is None:raise ContractError('Repair catalogue is required')
                router.require(action['repair'])
    results=[]
    def perform(action,mode,identity,failure=None):
        if 'repair' in action:return router.invoke(identity,mode,params,failure,env)
        return run(action,cwd=catalogue.path.parent,environ=env)
    for item in items:
        if operation!='check' and item['kind']!=operation:continue
        check=perform(item['check'],'check',item['id'])
        result={'id':item['id'],'kind':item['kind'],'initial_check':check,'status':'satisfied'}
        if check['status']!='passed':
            result['status']='action_required'
            failure={'stage':'check','result':check}
            if operation!='check' and not dry_run:
                applied=perform(item['apply'],'apply',item['id'],failure)
                final=perform(item['check'],'check',item['id'])
                result.update(apply=applied,final_check=final)
                result['status']='repaired' if applied['status']==final['status']=='passed' else 'failed'
                failure={'stage':'apply' if applied['status']!='passed' else 'final_check','result':applied if applied['status']!='passed' else final}
            elif dry_run:result['planned_apply']=item['apply']
            if result['status'] not in ('satisfied','repaired'):
                recommendation=item['recommendation']
                if isinstance(recommendation,str):result['recommendation']=recommendation
                else:
                    rec=perform(recommendation,'recommend',item['id'],failure)
                    result['recommendation_result']=rec
                    result['recommendation']=rec.get('response',{}).get('recommendation') or f'Требование {item["id"]} не выполнено; инструмент рекомендаций завершился с ошибкой.'
        results.append(result)
    states={r['status'] for r in results}
    status='failed' if 'failed' in states else 'action_required' if 'action_required' in states else 'repaired' if 'repaired' in states else 'ready' if results else 'not_required'
    visible={k:('[REDACTED]' if raw['parameters'][k].get('secret') else v) for k,v in params.items()}
    return redact({'schema':'environment-maintenance/result/v1','command':operation,'dry_run':dry_run,
                   'status':status,'exit_code':4 if status=='failed' else 3 if status=='action_required' else 0,
                   'parameters':visible,'parameter_sources':origins,'requirements':results},secrets)
