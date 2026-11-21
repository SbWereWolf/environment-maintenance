"""Test-owned observer of independently installed package and actual facade use."""
import importlib.abc
import importlib.metadata
import json
from pathlib import Path
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

mode, target, fixture, workspace = sys.argv[1:]
sys.path.insert(0, target)
distribution = importlib.metadata.distribution('command-execution')
assert distribution.version == '2.0.10'
# Declared installation requirements are observed independently of ambient imports.
declared = [Requirement(value) for value in (distribution.requires or [])]
assert not any(canonicalize_name(value.name) == 'environment-maintenance'
               for value in declared), 'Independent package declares its consumer as a dependency'
expected_requirements = {'jsonpatch': '>=1.36', 'jsonpointer': '>=3.4'}
for name, expected_specifier in expected_requirements.items():
    matching = [value for value in declared if canonicalize_name(value.name) == name]
    assert len(matching) == 1, 'Required runtime dependency missing or ambiguous: ' + name
    assert str(matching[0].specifier) == expected_specifier
    assert matching[0].marker is None, 'Required runtime dependency is conditional: ' + name
    assert not matching[0].extras, 'Unexpected required dependency extras: ' + name


class NoEnvironmentDependency(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'environment_maintenance' or fullname.startswith('environment_maintenance.'):
            raise AssertionError('Independent command library imports its consumer')

if mode == 'independent':
    sys.meta_path.insert(0, NoEnvironmentDependency())

import command_execution as shared
assert Path(shared.__file__).is_relative_to(Path(target))

if mode == 'independent':
    plan, issues = shared.CommandPlanner().compile({'commands': [
        {'id': 'probe', 'argv': [sys.executable, '-B', fixture]},
    ]})
    assert not issues
    result = shared.ChainCoordinator(plan).run(None)
    row, = result.commands
    assert result.status == 'failed'
    assert row.raw.returncode == 7
    assert row.raw.stdout == b'package-out\x00\xff'
    assert row.raw.stderr == b'package-err\xfe'
    print('independent-package-contract-ok')
    raise SystemExit(0)

import environment_maintenance as api
from environment_maintenance.actions.interpreters import exit_result

assert Path(api.__file__).is_relative_to(Path(target))
consumer = importlib.metadata.distribution('environment-maintenance')
selected = [Requirement(value) for value in (consumer.requires or [])
            if canonicalize_name(Requirement(value).name) == 'command-execution']
assert len(selected) == 1 and str(selected[0].specifier) == '==2.0.10'
assert distribution.version in selected[0].specifier

# Observe the real process creation and its call-stack provenance, without
# replacing a late-bound attribute or prescribing when a runner is captured.
launches = []
shared_root = Path(shared.__file__).parent

def observe_launch(event, arguments):
    if event != 'subprocess.Popen':
        return
    frame = sys._getframe().f_back
    files = []
    while frame is not None:
        files.append(frame.f_code.co_filename)
        frame = frame.f_back
    launches.append((arguments, files))

sys.addaudithook(observe_launch)
command = json.loads((Path(fixture).parent / 'action.json').read_text())['commands'][0]
command['argv'] = [sys.executable, '-B', fixture]
prepared = api.plan_action({'commands': [command]}, {'work': workspace},
                           base_dir=workspace, interpreters={'exit': exit_result})
assert prepared['commands'][0]['cwd'] == workspace
assert not launches
result = api.execute_action({'commands': [command]}, {'work': workspace},
                            base_dir=workspace, interpreters={'exit': exit_result})
assert len(launches) == 1
arguments, execution_files = launches[0]
launcher, script, child_workdir, env_count, *child_arguments = arguments[1]
assert launcher == 'bash'
assert Path(script) == Path(api.__file__).parent / 'resources/commands/invoke.bash'
assert child_workdir == workspace
assert env_count == '0'
assert child_arguments == command['argv']
assert any(Path(name).is_relative_to(shared_root) for name in execution_files), (
    'Real child launch did not traverse the installed shared implementation')
assert result['status'] == 'succeeded'
row = result['commands'][0]
assert row['exit_code'] == 7
assert row['stdout'] == b'package-out\x00\xff'
assert row['stderr'] == b'package-err\xfe'
assert row['interpretation'] == {'success': True, 'value': 7, 'error': None}
config = Path(workspace) / 'main.json'
operation = Path(workspace) / 'operation.json'
config.write_text(json.dumps({'operations': {'infra': 'operation.json'}}))
operation.write_text(json.dumps({'requirements': [{'id': 'first'}], 'metadata': 'keep'}))
assert api.list_requirement_ids(config, 'infra') == ['first']
api.add_requirement(config, 'infra', {'id': 'second'})
assert api.read_requirements(config, 'infra', 'all') == [{'id': 'first'}, {'id': 'second'}]
api.update_requirement(config, 'infra', 'second', [{'op': 'add', 'path': '/value', 'value': 9}])
assert api.read_requirements(config, 'infra', ['second']) == [{'id': 'second', 'value': 9}]
api.delete_requirement(config, 'infra', 'first')
assert api.list_requirement_ids(config, 'infra') == ['second']
api.clear_requirements(config, 'infra')
assert api.read_requirements(config, 'infra', 'all') == []
assert json.loads(operation.read_text())['metadata'] == 'keep'
print('original-consumer-use-ok')
