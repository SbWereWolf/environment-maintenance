"""Read the exact installed distribution through a clean external entry point."""
import json
from pathlib import Path
import sys
from threading import Event

installed, fixtures, workspace = map(Path, sys.argv[1:])
sys.path.insert(0, str(installed))
import command_execution

assert Path(command_execution.__file__).resolve().is_relative_to(installed.resolve())
for name in ('execute_chain', 'plan_chain'):
    assert callable(getattr(command_execution, name, None)), f'NEW-CHAIN-CONTRACT: missing installed {name}'
row = json.loads((fixtures / 'command.json').read_text())
row['argv'] = [sys.executable, str(fixtures / 'child.py'), str(workspace / 'seen.json'), 'echo', '7']
class Wire:
    def interpret(self, raw, options):
        return {'success': raw['exit_code'] == 7, 'error': None, 'value': None,
                'next_input': json.loads(raw['stdout'])}
initial = {'step': 'start', 'nested': [1]}
parameters = {}
arguments = dict(base_dir=workspace, input_data=initial, interpreters={'result': Wire()})
plan = command_execution.plan_chain({'commands': [row]}, parameters, **arguments)
assert plan['commands'][0]['argv'] == row['argv']
assert not (workspace / 'seen.json').exists()
result = command_execution.execute_chain({'commands': [row]}, parameters, **arguments)
assert result['data'] == {'step': 'child-changed', 'nested': [1]}
assert result['commands'][0]['stderr'] == b'err\x00\xfe' * 32768
row['mode'] = 'async'
done = Event()
records = []
def observe(record):
    records.append(record)
    done.set()
result = command_execution.execute_chain({'commands': [row]}, parameters,
                                          on_result=observe, **arguments)
assert result['data'] == initial
assert done.wait(10), 'installed async consumer never received completion'
assert records[0]['input_data'] == initial
assert records[0]['exit_code'] == 7
print('installed-chain-contract-ok')
