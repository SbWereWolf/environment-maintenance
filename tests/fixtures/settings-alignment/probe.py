"""Read-only independent observer of real application settings and process order."""
import json
from pathlib import Path
import sys


target, trace, phase = sys.argv[1:]
document = json.loads(Path(target).read_text(encoding='utf-8'))
items = {row['id']: row for row in document['requirements']}
observation = dict(phase=phase,
    writer=items['writer']['commands'][0]['env']['QUEUE_NAME'],
    reader=items['reader']['commands'][0]['env']['QUEUE_NAME'])
with Path(trace).open('a', encoding='utf-8') as stream:
    stream.write(json.dumps(observation) + '\n')
sys.stdout.buffer.write(b'\xff' + phase.encode() + b'\x00\n')
sys.stderr.buffer.write(b'probe:' + phase.encode() + b'\n')
