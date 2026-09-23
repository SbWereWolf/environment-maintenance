"""Create an absent SQLite schema; diagnose but never rebuild an existing database."""
import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from ..shared.filesystem import lexical_path,regular_or_missing
from ..shared.protocol import result,recommend,serve,RepairError
TEMPLATES={
 'missing':'База {path} отсутствует. Создайте её по выбранной декларации {schema} через infra.',
 'corrupt':'База {path} повреждена. Сохраните её копию; используйте подтверждённый backup или профильный ремонт. Автоматического удаления нет.',
 'version':'Версия базы {path} не совпадает с декларацией {schema}. Нужна согласованная миграция её владельца; пересоздание запрещено.',
 'schema':'Структура базы {path} не совпадает с декларацией {schema}. Проверьте совместимость версии приложения; данные не изменены.',
 'foreign_keys':'В базе {path} нарушены внешние ключи. Требуется ремонт прикладных данных владельцем схемы.',
 'symlink':'Путь базы {path} содержит символическую ссылку. Выберите реальный путь; ремонт не выполнялся.',
 'unknown':'Проверьте доступ к {path}, декларацию {schema} и исходную ошибку. Существующая база не пересоздаётся.'}


def shape(connection):
    return connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()


def restrict_schema(connection):
    # Even a check must not let schema SQL ATTACH/VACUUM INTO external files.
    denied={sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH,sqlite3.SQLITE_PRAGMA}
    connection.set_authorizer(lambda op,a,b,db,trigger: sqlite3.SQLITE_DENY if op in denied else sqlite3.SQLITE_OK)


def load_spec(path):
    spec=json.loads(lexical_path(path).read_text())
    if not isinstance(spec,dict) or set(spec)!={'version','sql'} or type(spec['version']) is not int or not 0<=spec['version']<2**31 or not isinstance(spec['sql'],str):
        raise RepairError('invalid_schema','Expected explicit version and trusted initialization SQL')
    with sqlite3.connect(':memory:') as c:
        restrict_schema(c);c.executescript(spec['sql']);expected=shape(c)
    return spec,expected


def inspect(path,spec,expected):
    if not regular_or_missing(path):return result('action_required','missing')
    try:
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=1) as c:
            if c.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:return result('action_required','corrupt')
            if c.execute('PRAGMA user_version').fetchone()[0]!=spec['version']:return result('action_required','version')
            if shape(c)!=expected:return result('action_required','schema')
            if c.execute('PRAGMA foreign_key_check').fetchall():return result('action_required','foreign_keys')
    except sqlite3.DatabaseError as exc:return result('action_required','corrupt',detail=str(exc))
    return result('satisfied','ok')


def handle(args,r):
    if r['mode']=='recommend':return recommend(r,TEMPLATES,{'path':args.path,'schema':args.schema})
    path=lexical_path(args.path)
    try:spec,expected=load_spec(args.schema)
    except sqlite3.DatabaseError as exc:return result('action_required','invalid_schema',detail=str(exc))
    before=inspect(path,spec,expected)
    if r['mode']=='apply' and before['code']=='missing':
        fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent);os.close(fd)
        temp=Path(name)
        try:
            with sqlite3.connect(temp) as c:
                restrict_schema(c);c.executescript(spec['sql']);c.set_authorizer(None);c.execute('PRAGMA user_version='+str(spec['version']))
            checked=inspect(temp,spec,expected)
            if checked['status']!='satisfied':return checked
            os.link(temp,path)  # Exclusive creation, existing database never replaced.
        finally:temp.unlink()
        after=inspect(path,spec,expected)
        if after['status']=='satisfied':after['status']='repaired'
        return after
    return before


def main():
    p=argparse.ArgumentParser(description='SQLite schema requirement repair module')
    p.add_argument('--path',required=True);p.add_argument('--schema',required=True)
    return serve(p,handle)
if __name__=='__main__':raise SystemExit(main())
