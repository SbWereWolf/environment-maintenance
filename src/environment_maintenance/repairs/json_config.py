"""Create missing JSON configuration from an explicit template; never overwrite it."""
import argparse
import json
from ..catalogue import read_json
from ..shared.filesystem import lexical_path,regular_or_missing,create_only
from ..shared.protocol import result,recommend,serve
TEMPLATES={
 'invalid_json':'Конфигурация {path} не является корректным JSON. Исправьте синтаксис; исходные байты сохранены.',
 'missing':'Создайте отсутствующий JSON-конфиг {path} из явно выбранного шаблона {template}.',
 'missing_keys':'Добавьте обязательные поля в JSON-конфиг {path}; пользовательские значения не заменяются шаблоном.',
 'symlink':'Укажите реальный файл JSON-конфигурации вместо пути через символическую ссылку: {path}.',
 'unknown':'Проверьте JSON-конфиг {path}, шаблон {template} и исходную ошибку. Автоматической перезаписи нет.'}


def inspect(path,required):
    if not regular_or_missing(path):return result('action_required','missing')
    try:value=read_json(path)
    except (ValueError,UnicodeError):return result('action_required','invalid_json')
    if not isinstance(value,dict):return result('action_required','invalid_json')
    missing=sorted(set(required)-value.keys())
    return result('action_required','missing_keys',missing=missing) if missing else result('satisfied','ok')


def handle(args,r):
    if r['mode']=='recommend':return recommend(r,TEMPLATES,{'path':args.path,'template':args.template})
    path=lexical_path(args.path);before=inspect(path,args.required)
    if r['mode']=='apply' and before['code']=='missing':
        template=lexical_path(args.template);valid=inspect(template,args.required)
        if valid['status']!='satisfied':return result('action_required','invalid_template',detail=valid)
        create_only(path,template.read_bytes())
        after=inspect(path,args.required)
        if after['status']=='satisfied':after['status']='repaired'
        return after
    return before


def main():
    p=argparse.ArgumentParser(description='JSON configuration requirement repair module')
    p.add_argument('--path',required=True);p.add_argument('--template',required=True)
    p.add_argument('--required',action='append',default=[])
    return serve(p,handle)
if __name__=='__main__':raise SystemExit(main())
