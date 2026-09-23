"""Standalone CLI, independent from the Poise router."""
import argparse
import json
from pathlib import Path
import sys
from .catalogue import load_catalogue,read_json,ContractError
from .engine import execute


def main(argv=None):
    p=argparse.ArgumentParser(description='Проверка и обслуживание требований среды')
    p.add_argument('command',choices=['infra','deps','check'])
    p.add_argument('--catalog',required=True,type=Path)
    p.add_argument('--repairs',type=Path)
    p.add_argument('--values',action='append',default=[],type=Path)
    p.add_argument('--set',dest='overrides',action='append',default=[])
    p.add_argument('--dry-run',action='store_true')
    args=p.parse_args(argv)
    try:
        values={}
        for f in args.values:values.update(read_json(f))
        result=execute(load_catalogue(args.catalog),args.command,values=values,overrides=args.overrides,
                       dry_run=args.dry_run,repair_catalog=args.repairs)
    except ContractError as e:
        result={'schema':'environment-maintenance/result/v1','status':'invalid','exit_code':2,'error':str(e)}
    print(json.dumps(result,ensure_ascii=False,indent=2));return result['exit_code']
