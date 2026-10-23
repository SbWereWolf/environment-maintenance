"""A real interactive test worker; observable files are independent of the launcher."""
import json
import os
from pathlib import Path
import signal
import sys

directory, label = Path(sys.argv[1]), sys.argv[2]


def save(kind, value):
    path = directory / (label + '.' + kind + '.json')
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value), encoding='utf-8')
    temporary.replace(path)


def stopped(number, frame):
    save('stopped', dict(label=label, signal=number, pid=os.getpid()))
    raise SystemExit(0)


signal.signal(signal.SIGINT, stopped)
print('ENV2 visible worker ' + label, flush=True)
save('ready', dict(label=label, pid=os.getpid(), parent=os.getppid(),
    tty=os.ttyname(0), window=os.environ['WINDOWID'], cwd=os.getcwd(),
    token=os.environ.get('LAUNCH_TOKEN')))
for line in sys.stdin:
    text = line.rstrip('\n')
    print(label + ': ' + text, flush=True)
    save('reply', dict(label=label, text=text, pid=os.getpid()))
