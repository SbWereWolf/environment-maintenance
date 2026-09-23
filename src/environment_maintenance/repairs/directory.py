"""Directory availability and permissions; no recursive ownership or chmod repair."""
import argparse
import os
import stat
from ..shared.filesystem import lexical_path
from ..shared.protocol import result,recommend,serve
TEMPLATES={
    'missing':'Создайте каталог {path} командой infra с этим требованием. Родитель должен уже существовать.',
    'permissions':'Проверьте владельца и режим каталога {path}. Автоматический chmod существующих данных запрещён.',
    'symlink':'Путь {path} содержит символическую ссылку. Укажите отдельный реальный каталог.',
    'unknown':'Проверьте каталог {path}, доступ и сообщение исходной ошибки. Существующие данные не удалены.'}


def inspect(path,mode):
    try:s=path.lstat()
    except FileNotFoundError:return result('action_required','missing')
    if not stat.S_ISDIR(s.st_mode):return result('action_required','wrong_type')
    if stat.S_IMODE(s.st_mode)!=mode or not os.access(path,os.R_OK|os.W_OK|os.X_OK):
        return result('action_required','permissions')
    return result('satisfied','ok')


def handle(args,request):
    if request['mode']=='recommend':return recommend(request,TEMPLATES,{'path':args.path})
    path=lexical_path(args.path);mode=int(args.permissions,8)
    if not 0<=mode<=0o777:raise ValueError('Permissions must be 0000..0777')
    before=inspect(path,mode)
    if request['mode']=='apply' and before['code']=='missing':
        path.mkdir(mode=mode)  # Parent is a separate declarative requirement.
        os.chmod(path,mode)
        after=inspect(path,mode)
        if after['status']=='satisfied':after['status']='repaired'
        return after
    return before


def main():
    p=argparse.ArgumentParser(description='Directory requirement repair module')
    p.add_argument('--path',required=True);p.add_argument('--permissions',required=True)
    return serve(p,handle)
if __name__=='__main__':raise SystemExit(main())
