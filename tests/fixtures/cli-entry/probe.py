"""External fixture tool records real invocation and reads protected app data."""
import json
import os
from pathlib import Path
import sys

events, tag, instance, token, port, zero, code, data = sys.argv[1:]
record = dict(tag=tag, instance=instance, token=token, port=port, zero=zero,
              cwd=os.getcwd(), marker=os.environ.get('RESOURCE_MARKER'),
              data=Path(data).read_text(encoding='utf-8'))
with Path(events).open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(record, ensure_ascii=False) + '\n')
print(tag)
raise SystemExit(int(code))
