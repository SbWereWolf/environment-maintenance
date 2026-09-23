"""The selected Python interpreter owns its version check and actionable diagnostics."""
import argparse
import sys
from ..shared.protocol import serve,result,recommend
TEMPLATES={
 'version':'Выбранный Python не входит в диапазон [{minimum}, {maximum}). Укажите совместимый исполняемый файл параметром python. Работающий интерпретатор не переустанавливается этим процессом.',
 'unknown':'Проверьте выбранный интерпретатор Python и диапазон [{minimum}, {maximum}). Установку другого runtime выполняет оператор или отдельный явно настроенный установщик.'}


def version(text):
    values=text.split('.')
    if not 1<=len(values)<=3 or not all(v.isdigit() for v in values):raise ValueError('Version must have 1..3 integer components')
    return tuple(map(int,values))+(0,)*(3-len(values))


def handle(args,r):
    low,high=version(args.minimum),version(args.maximum)
    if low>=high:raise ValueError('minimum must be lower than maximum')
    if r['mode']=='recommend':return recommend(r,TEMPLATES,{'minimum':args.minimum,'maximum':args.maximum})
    # Applying a runtime requirement must never replace a running interpreter.
    valid=low<=tuple(sys.version_info[:3])<high
    return result('satisfied' if valid else 'action_required','ok' if valid else 'version',observed='.'.join(map(str,sys.version_info[:3])))


def main():
    p=argparse.ArgumentParser(description='Selected Python runtime requirement module')
    p.add_argument('--minimum',required=True);p.add_argument('--maximum',required=True)
    return serve(p,handle)
if __name__=='__main__':raise SystemExit(main())
