"""Exercise only the installed public configuration API and observe file data."""
import json
from pathlib import Path
import sys
import environment_maintenance as api

main = Path(sys.argv[1])
original = main.read_bytes()
before = api.list_requirement_ids(main, 'deps')
api.add_requirement(main, 'deps', dict(id='created', flag=False))
api.update_requirement(main, 'deps', 'created', [
    dict(op='replace', path='/flag', value=0), dict(op='add', path='/extra', value=None)])
selected = api.read_requirements(main, 'deps', ['created'])
all_ids = [item['id'] for item in api.read_requirements(main, 'deps', 'all')]
api.delete_requirement(main, 'deps', 'created')
after_delete = api.list_requirement_ids(main, 'deps')
api.clear_requirements(main, 'deps')
after_clear = api.read_requirements(main, 'deps', 'all')
document = json.loads((main.parent / 'deps.json').read_text())
print(json.dumps(dict(before=before, selected=selected, all_ids=all_ids,
    after_delete=after_delete, after_clear=after_clear, owner=document['owner'],
    main_unchanged=main.read_bytes() == original)))
