"""Real local-entry contract; inputs and effect oracles have separate fixture owners."""
import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from environment_maintenance import prepare_resources
from v2_helpers import catalog, stateful_requirement


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures' / 'cli-entry'


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    path.chmod(0o640)


def command(tag):
    value = fixture('command.json')
    value['argv'][3] = tag
    return value


class SetupExit:
    def interpret(self, raw, options):
        ok = raw['exit_code'] == 0
        return dict(success=ok, value=None, error=None if ok else 'fixture deployment failed')


@pytest.fixture(scope='session')
def runtime_pool(tmp_path_factory):
    """Deploy two actual entries/runtimes through a declared SDK operation."""
    installed = distribution('environment-maintenance')
    for source in (ROOT / 'src/environment_maintenance').rglob('*.py'):
        deployed = Path(installed.locate_file(source.relative_to(ROOT / 'src')))
        assert deployed.read_bytes() == source.read_bytes(), (
            'Prerequisite: install the current source wheel before tests: ' + str(source))
    pool = tmp_path_factory.mktemp('entry installations with spaces')
    for name in ('runtime-install-main.json', 'runtime-install.json'):
        shutil.copy2(FIXTURES / name, pool / name)
    values = dict(python=sys.executable, installer=str(FIXTURES / 'install_runtime.py'),
                  source_entry=str(ROOT / 'start-app'), source_runtime=sys.prefix,
                  plugin=str(FIXTURES / 'plugins.py'), probe=str(FIXTURES / 'probe.py'),
                  pool=str(pool), install_a=str(pool / 'A'), install_b=str(pool / 'B'))
    result = prepare_resources(pool / 'runtime-install-main.json', 'infra', 'all',
        values, base_dir=pool, interpreters={'exit': SetupExit()})
    assert result['status'] == 'succeeded', result
    apps = {}
    for name in ('A', 'B'):
        root = pool / name
        python = root / '.venv/bin/python'
        probe = 'import environment_maintenance as m; print(m.__file__); print(m.__version__)'
        identity = subprocess.check_output([str(python), '-I', '-B', '-c', probe], text=True)
        module, version = identity.splitlines()
        assert Path(module).is_relative_to(root / '.venv')
        assert (root / 'start-app').read_bytes() == (ROOT / 'start-app').read_bytes()
        apps[name] = SimpleNamespace(name=name, root=root, entry=root / 'start-app',
            main=root / 'start-app.json', parameters=root / 'parameters.json',
            workspace=root / 'workspace', events=root / 'events.jsonl',
            data=root / 'data.txt', python=python, module=Path(module), version=version)
    return apps


def reset_profile(app):
    app.workspace.mkdir(exist_ok=True)
    app.events.unlink(missing_ok=True)
    app.data.write_text('keep existing data\n', encoding='utf-8')
    app.data.chmod(0o600)
    write(app.main, fixture('main.json'))
    values = fixture('parameters.json')
    values.update(fixture('instances.json')[app.name])
    values.update(python=str(app.python), probe=str(app.root / 'tools/probe.py'),
                  events=str(app.events), data=str(app.data))
    write(app.parameters, values)
    for operation, resources in fixture('operation-inputs.json').items():
        requirements = []
        for resource in resources:
            row = dict(id=resource['id'], commands=[command(tag) for tag in resource['tags']])
            if 'presence' in resource:
                row['checks'] = dict(presence=dict(commands=[command(resource['presence'])]))
                if 'availability' in resource:
                    row['checks']['availability'] = dict(commands=[command(resource['availability'])])
            requirements.append(row)
        write(app.root / (operation + '.json'), dict(requirements=requirements))


@pytest.fixture
def apps(runtime_pool):
    for app in runtime_pool.values():
        reset_profile(app)
    return runtime_pool


def invoke(app, operation, *arguments, cwd=None):
    return subprocess.run([str(app.entry), operation, *map(str, arguments)],
        cwd=cwd or app.root, capture_output=True, timeout=20)


def events(app):
    if not app.events.exists():
        return []
    return [json.loads(line) for line in app.events.read_text(encoding='utf-8').splitlines()]


def expected_event(app, tag, *, cwd=None, token=None):
    expected = fixture('expected-event.json')[app.name]
    expected.update(tag=tag, cwd=str(cwd or app.workspace))
    if token is not None:
        expected['token'] = token
    return expected


def protected(app, additional=()):
    paths = list(app.root.glob('*.json')) + list((app.root / 'values').glob('*.json'))
    paths += [app.data, app.entry, app.python, app.module, app.module.parent / 'cli.py']
    paths += list(additional)
    return {str(path): (hashlib.sha256(path.read_bytes()).hexdigest(),
                        path.stat().st_mode & 0o777) for path in paths}


def assert_runtime(result, app):
    """Observe the interpreter's CLI environment, independently of probe argv."""
    if result['operation'] == 'check':
        actions = [row['presence'] for row in result['resources']]
        actions += [row['availability']['result'] for row in result['resources']
                    if row['availability']['result'] is not None]
        actions += [row['result'] for row in result['checks']]
    else:
        actions = [row['result'] for row in result['requirements']]
    commands = [record for action in actions for record in action['commands']]
    if commands:
        actual = {record['interpretation']['value']['engine_runtime'] for record in commands}
        assert actual == {str(app.root / '.venv')}


def success(completed, operation, app):
    assert completed.returncode == 0, completed.stderr.decode(errors='replace')
    assert completed.stderr == b''
    result = json.loads(completed.stdout)
    assert result['operation'] == operation and result['status'] == 'succeeded'
    assert_runtime(result, app)
    return result


def assert_operation_effects(app, operation, completed):
    result = success(completed, operation, app)
    expected = fixture('expected.json')[operation]
    records = result['resources'] if operation == 'check' else result['requirements']
    assert [record['id'] for record in records] == expected['ids']
    if operation == 'check':
        assert [record['id'] for record in result['checks']] == ['consistency']
    assert events(app) == [expected_event(app, tag) for tag in expected['tags']]


@pytest.mark.parametrize('operation', ['infra', 'deps', 'adjust', 'check', 'run'])
def test_flagless_operation_uses_declared_values_and_exact_effects(apps, operation):
    app = apps['A']
    before = protected(app)
    assert_operation_effects(app, operation, invoke(app, operation))
    assert protected(app) == before


@pytest.mark.parametrize('operation', ['infra', 'deps', 'adjust', 'check', 'run'])
def test_fixture_full_explicit_control_is_executable(apps, operation):
    """Separate setup/control PASS from missing flagless behavior RED."""
    app = apps['A']
    before = protected(app)
    arguments = ['--config', app.main, '--parameters', app.parameters,
                 '--base-dir', app.workspace]
    if operation != 'check':
        arguments += ['--requirements', json.dumps(fixture('expected.json')[operation]['ids'])]
    assert_operation_effects(app, operation, invoke(app, operation, *arguments))
    assert protected(app) == before


def alternate_main(app, target, *, configured=True):
    main = fixture('main.json')
    for operation in ('infra', 'deps', 'adjust', 'check', 'run'):
        main['operations'][operation] = str(app.root / (operation + '.json'))
    if not configured:
        del main['invocation']
    write(target, main)


def parameters_with_token(app, target, token):
    values = json.loads(app.parameters.read_text(encoding='utf-8'))
    values['token'] = token
    write(target, values)


def ordinary_again(app, operation, *, cwd=None):
    """Clear only observation output, without resetting any configuration."""
    app.events.unlink(missing_ok=True)
    assert_operation_effects(app, operation, invoke(app, operation, cwd=cwd))


def test_relative_config_keeps_caller_anchor_and_main_relative_defaults(apps, tmp_path):
    app = apps['A']
    caller = tmp_path / 'caller'
    main_dir = caller / 'profiles'
    main = main_dir / 'alternate.json'
    alternate_main(app, main)
    parameters_with_token(app, main_dir / 'parameters.json', 'main-parameter')
    parameters_with_token(app, caller / 'parameters.json', 'caller-decoy')
    workspace = main_dir / 'workspace'
    workspace.mkdir()
    selected = [main, main_dir / 'parameters.json', caller / 'parameters.json']
    before = protected(app, selected)
    success(invoke(app, 'deps', '--config', 'profiles/alternate.json', cwd=caller), 'deps', app)
    assert events(app) == [expected_event(app, 'deps', cwd=workspace, token='main-parameter')]
    assert protected(app, selected) == before
    ordinary_again(app, 'deps', cwd=caller)
    assert protected(app, selected) == before


def test_relative_parameter_override_keeps_other_installation_defaults(apps, tmp_path):
    app = apps['A']
    caller = tmp_path / 'caller'
    parameters_with_token(app, caller / 'values/chosen.json', 'caller-parameter')
    parameters_with_token(app, app.root / 'values/chosen.json', 'installation-decoy')
    selected = [caller / 'values/chosen.json']
    before = protected(app, selected)
    success(invoke(app, 'deps', '--parameters', 'values/chosen.json', cwd=caller), 'deps', app)
    assert events(app) == [expected_event(app, 'deps', token='caller-parameter')]
    assert protected(app, selected) == before
    ordinary_again(app, 'deps', cwd=caller)
    assert protected(app, selected) == before


def test_base_directory_override_retains_parameter_and_selection_defaults(apps, tmp_path):
    app = apps['A']
    workspace = tmp_path / 'explicit workspace'
    workspace.mkdir()
    before = protected(app)
    success(invoke(app, 'infra', '--base-dir', workspace), 'infra', app)
    assert events(app) == [expected_event(app, tag, cwd=workspace)
                          for tag in ['infra-first', 'infra-second', 'infra-secondary']]
    assert protected(app) == before
    ordinary_again(app, 'infra')
    assert protected(app) == before


def test_selection_override_retains_parameter_and_base_defaults(apps):
    app = apps['A']
    before = protected(app)
    result = success(invoke(app, 'infra', '--requirements', '["secondary","base"]'), 'infra', app)
    assert [item['id'] for item in result['requirements']] == ['secondary', 'base']
    assert events(app) == [expected_event(app, tag)
                          for tag in ['infra-secondary', 'infra-first', 'infra-second']]
    assert protected(app) == before
    ordinary_again(app, 'infra')
    assert protected(app) == before


@pytest.mark.parametrize('case', fixture('selection-cases.json'), ids=['all', 'empty'])
def test_configured_all_and_empty_selection_are_explicit_values(apps, case):
    app = apps['A']
    main = json.loads(app.main.read_text(encoding='utf-8'))
    main['invocation']['requirements']['infra'] = case['selection']
    write(app.main, main)
    before = protected(app)
    result = success(invoke(app, 'infra'), 'infra', app)
    assert [item['id'] for item in result['requirements']] == case['ids']
    assert events(app) == [expected_event(app, tag) for tag in case['tags']]
    assert protected(app) == before


@pytest.mark.parametrize('case', fixture('selection-cases.json'), ids=['all', 'empty'])
def test_all_and_empty_selection_overrides_apply_only_to_one_call(apps, case):
    app = apps['A']
    selection = 'all' if case['selection'] == 'all' else json.dumps(case['selection'])
    before = protected(app)
    result = success(invoke(app, 'infra', '--requirements', selection), 'infra', app)
    assert [item['id'] for item in result['requirements']] == case['ids']
    assert events(app) == [expected_event(app, tag) for tag in case['tags']]
    assert protected(app) == before
    ordinary_again(app, 'infra')
    assert protected(app) == before


def test_full_explicit_form_preserves_caller_relative_paths_without_invocation(apps, tmp_path):
    app = apps['A']
    caller = tmp_path / 'caller'
    alternate_main(app, caller / 'profiles/legacy.json', configured=False)
    parameters_with_token(app, caller / 'values/explicit.json', 'explicit-parameter')
    selected = [caller / 'profiles/legacy.json', caller / 'values/explicit.json']
    before = protected(app, selected)
    result = success(invoke(app, 'infra', '--config', 'profiles/legacy.json',
        '--parameters', 'values/explicit.json', '--base-dir', app.workspace,
        '--requirements', '["secondary"]', cwd=caller), 'infra', app)
    assert [item['id'] for item in result['requirements']] == ['secondary']
    assert events(app) == [expected_event(app, 'infra-secondary', token='explicit-parameter')]
    assert protected(app, selected) == before
    ordinary_again(app, 'infra', cwd=caller)
    assert protected(app, selected) == before


def test_two_absolute_local_entries_keep_other_installation_unchanged(apps, tmp_path):
    a, b = apps['A'], apps['B']
    before_b = protected(b)
    success(invoke(a, 'run', cwd=tmp_path), 'run', a)
    assert events(a) == [expected_event(a, 'run')]
    assert events(b) == [] and protected(b) == before_b
    before_a = protected(a)
    success(invoke(b, 'run', cwd=tmp_path), 'run', b)
    assert events(b) == [expected_event(b, 'run')]
    assert events(a) == [expected_event(a, 'run')] and protected(a) == before_a
    assert a.module != b.module


def test_runtime_oracle_distinguishes_engine_from_external_probe_parameters(apps, tmp_path):
    """A/configB is valid, but its observed engine must not be mistaken for B."""
    a, b = apps['A'], apps['B']
    before_a, before_b = protected(a), protected(b)
    result = success(invoke(a, 'run', '--config', b.main, '--parameters', b.parameters,
        '--base-dir', b.workspace, '--requirements', '["launch"]', cwd=tmp_path), 'run', a)
    assert events(b) == [expected_event(b, 'run')] and events(a) == []
    with pytest.raises(AssertionError):
        assert_runtime(result, b)
    assert protected(a) == before_a and protected(b) == before_b


def test_disposable_runtime_cleanup_preserves_short_entry_and_settings(apps):
    app = apps['A']
    temporary = app.root / '.runtime'
    temporary.mkdir(exist_ok=True)
    (temporary / 'session.txt').write_text('disposable', encoding='utf-8')
    before = protected(app)
    success(invoke(app, 'deps'), 'deps', app)
    shutil.rmtree(temporary)
    success(invoke(app, 'deps'), 'deps', app)
    assert events(app) == [expected_event(app, 'deps'), expected_event(app, 'deps')]
    assert protected(app) == before


@pytest.mark.parametrize('kind', ['missing', 'malformed'])
def test_unavailable_main_has_named_diagnostic_and_no_effects(apps, kind):
    app = apps['A']
    if kind == 'missing':
        app.main.unlink()
    else:
        app.main.write_text('{ invalid json', encoding='utf-8')
    completed = invoke(app, 'infra')
    assert completed.returncode == 2
    assert str(app.main).encode() in completed.stderr
    assert events(app) == []


@pytest.mark.parametrize('field', ['parameters', 'base_dir', 'requirements'])
def test_missing_needed_invocation_setting_is_not_an_implicit_default(apps, field):
    app = apps['A']
    main = json.loads(app.main.read_text(encoding='utf-8'))
    del main['invocation'][field]
    write(app.main, main)
    completed = invoke(app, 'infra')
    assert completed.returncode == 2
    diagnostic = completed.stderr.decode(errors='replace').strip().splitlines()[-1]
    assert field in diagnostic
    assert events(app) == []


@pytest.mark.parametrize('case', fixture('invalid-defaults.json'), ids=lambda case: case['case'])
def test_unusable_invocation_shape_has_diagnostic_and_no_effects(apps, case):
    app = apps['A']
    main = json.loads(app.main.read_text(encoding='utf-8'))
    selected = main
    for part in case['path'][:-1]:
        selected = selected[part]
    if case.get('delete', False):
        del selected[case['path'][-1]]
    else:
        selected[case['path'][-1]] = case['value']
    write(app.main, main)
    before = protected(app)
    completed = invoke(app, 'infra')
    assert completed.returncode == 2
    diagnostic = completed.stderr.decode(errors='replace').strip().splitlines()[-1]
    for term in case['diagnostic']:
        assert term in diagnostic
    assert events(app) == [] and protected(app) == before


def test_explicit_relative_cli_base_directory_stays_invalid(apps):
    app = apps['A']
    before = protected(app)
    completed = invoke(app, 'infra', '--config', app.main, '--parameters', app.parameters,
                       '--base-dir', 'workspace', '--requirements', '["base"]')
    assert completed.returncode == 2
    assert b'absolute' in completed.stderr.lower()
    assert events(app) == [] and protected(app) == before


def test_external_failure_keeps_attempted_records_and_stops_later_commands(apps):
    app = apps['A']
    path = app.root / 'infra.json'
    document = json.loads(path.read_text(encoding='utf-8'))
    base = next(item for item in document['requirements'] if item['id'] == 'base')
    base['commands'][1]['argv'][8] = '7'
    write(path, document)
    completed = invoke(app, 'infra')
    assert completed.returncode == 1, completed.stderr.decode(errors='replace')
    result = json.loads(completed.stdout)
    assert result['status'] == 'failed'
    assert_runtime(result, app)
    assert [item['id'] for item in result['requirements']] == ['base']
    assert [item['exit_code'] for item in result['requirements'][0]['result']['commands']] == [0, 7]
    assert events(app) == [expected_event(app, 'infra-first'), expected_event(app, 'infra-second')]


@pytest.mark.parametrize('operation,initial,log_expected', [
    ('check', 'satisfied', ['check']),
    ('run', 'missing', ['check', 'install', 'check']),
])
def test_explicit_catalog_ignores_present_ordinary_main(apps, tmp_path, operation,
                                                     initial, log_expected):
    app = apps['A']
    item, state, log = stateful_requirement(tmp_path, initial)
    catalog(tmp_path, [item])
    before = protected(app)
    completed = invoke(app, operation, '--catalog-dir', 'catalog-v2', cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr.decode(errors='replace')
    result = json.loads(completed.stdout)
    assert result['status'] == 'ready' and result['exit_code'] == 0
    assert log.read_text(encoding='utf-8').splitlines() == log_expected
    assert state.read_text(encoding='utf-8') == 'satisfied'
    assert events(app) == [] and protected(app) == before
