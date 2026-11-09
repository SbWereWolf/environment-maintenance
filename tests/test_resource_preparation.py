"""Preparation contract through public API, real CLI and external effects."""
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

import environment_maintenance as public_api


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures' / 'resource-preparation'


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def payload(name):
    return bytes.fromhex((FIXTURES / name).read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def api():
    function = getattr(public_api, 'prepare_resources', None)
    assert callable(function), 'Missing required public resource preparation API'
    return function


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    workspace = tmp_path / 'serviced root with spaces'
    (workspace / 'nested').mkdir(parents=True)
    config_dir = tmp_path / 'configuration'
    config_dir.mkdir()
    for name in ('app.json', 'infra.json', 'deps.json'):
        shutil.copyfile(FIXTURES / name, config_dir / name)
    plugins_dir = tmp_path / 'external plugins'
    plugins_dir.mkdir()
    shutil.copyfile(FIXTURES / 'plugins.py', plugins_dir / 'env2_test_plugins.py')
    parameters = fixture('parameters.json')
    parameters.update(python=sys.executable, probe=str(FIXTURES / 'probe.py'),
                      events=str(workspace / 'events.jsonl'),
                      stdout_file=str(FIXTURES / 'stdout.hex'),
                      stderr_file=str(FIXTURES / 'stderr.hex'))
    values = config_dir / 'values.json'
    write_json(values, parameters)
    objects = runpy.run_path(str(FIXTURES / 'plugins.py'))
    monkeypatch.setenv('ENV2_HOST_ONLY', 'host must not reach commands')
    monkeypatch.setenv('RESOURCE_VALUE', 'host must not replace selected values')
    return SimpleNamespace(root=workspace, main=config_dir / 'app.json',
        infra=config_dir / 'infra.json', deps=config_dir / 'deps.json', values=values,
        parameters=parameters, objects=objects, plugins=plugins_dir,
        interpreters={'chosen': objects['exit_result']},
        events=workspace / 'events.jsonl', foreign_cwd=tmp_path)


def invoke(s, operation='infra', selection='all', **changes):
    arguments = dict(config_path=s.main, operation=operation, selection=selection,
                     parameters=s.parameters, base_dir=s.root, interpreters=s.interpreters)
    arguments.update(changes)
    return api()(**arguments)


def run_cli(s, operation='infra', selection='all', *, arguments=None):
    if arguments is None:
        arguments = [operation, '--config', str(s.main), '--parameters', str(s.values),
                     '--base-dir', str(s.root), '--requirements',
                     selection if selection == 'all' else json.dumps(selection)]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / 'src'), str(s.plugins)]))
    completed = subprocess.run([sys.executable, '-B', '-m', 'environment_maintenance', *arguments],
                               cwd=s.foreign_cwd, env=env, capture_output=True, check=False)
    diagnostic = completed.stderr.decode('utf-8', errors='replace')
    recognized = not any(f"invalid choice: '{name}'" in diagnostic for name in ('infra', 'deps'))
    assert recognized, 'Missing required infra/deps CLI preparation'
    return completed


def events(s):
    if not s.events.exists():
        return []
    return [json.loads(line) for line in s.events.read_text(encoding='utf-8').splitlines()]


def assert_events(s, tags, *, scalar='42', token=None):
    token = s.parameters['token'] if token is None else token
    locations = fixture('expected-cwd.json')
    expected = []
    for tag in tags:
        item = fixture('expected-event.json')
        item.update(tag=tag, token=token, cwd=str(s.root / locations[tag]), value=token, scalar=scalar)
        expected.append(item)
    assert events(s) == expected


def assert_shape(result):
    shapes = fixture('shapes.json')
    assert set(result) == set(shapes['aggregate'])
    assert type(result['requirements']) is list
    for requirement in result['requirements']:
        assert set(requirement) == set(shapes['requirement'])
        assert type(requirement['id']) is str
        action = requirement['result']
        assert set(action) == set(shapes['action'])
        for record in action['commands']:
            assert set(record) == set(shapes['command'])
            assert set(record['invocation']) == set(shapes['invocation'])


def assert_streams(result, *, encoded=False, stdout=None, stderr=None):
    expected_stdout = payload('stdout.hex') if stdout is None else stdout
    expected_stderr = payload('stderr.hex') if stderr is None else stderr
    for requirement in result['requirements']:
        for record in requirement['result']['commands']:
            for key, expected in [('stdout', expected_stdout), ('stderr', expected_stderr)]:
                actual = record[key]
                if encoded:
                    assert set(actual) == {'encoding', 'data'}
                    assert actual['encoding'] == 'base64' and type(actual['data']) is str
                    assert base64.b64decode(actual['data'], validate=True) == expected
                else:
                    assert type(actual) is bytes and actual == expected


def assert_success(s, result, operation, identifiers, tags, *, encoded=False, codes=None):
    codes = {} if codes is None else codes
    assert_shape(result)
    assert result['operation'] == operation and result['status'] == 'succeeded'
    assert result['error'] is None
    assert [item['id'] for item in result['requirements']] == identifiers
    records = [record for item in result['requirements'] for record in item['result']['commands']]
    assert len(records) == len(tags)
    locations = fixture('expected-cwd.json')
    for record, tag in zip(records, tags, strict=True):
        expected = fixture('expected-invocation.json')
        # Fill only test-runtime locations/values; no production renderer is used.
        expected['argv'] = [sys.executable, str(FIXTURES / 'probe.py'), str(s.events), tag,
                            s.parameters['token'], s.parameters['stdout_file'],
                            s.parameters['stderr_file'], str(codes.get(tag, 0))]
        expected['cwd'] = str(s.root / locations[tag])
        expected['env']['RESOURCE_VALUE'] = s.parameters['token']
        assert record['invocation'] == expected
        assert type(record['exit_code']) is int and record['exit_code'] == codes.get(tag, 0)
        assert record['interpreter'] == dict(name='chosen', options=dict(accept=[codes.get(tag, 0)], tag='accepted'))
        assert record['interpretation']['success'] is True
        assert record['interpretation']['error'] is None and record['error'] is None
        assert record['interpretation']['value'] == dict(tag='accepted', code=codes.get(tag, 0))
    for item in result['requirements']:
        assert item['result']['status'] == 'succeeded' and item['result']['error'] is None
    assert_streams(result, encoded=encoded)
    assert_events(s, tags)


def edit(s, name, change):
    path = getattr(s, name)
    value = json.loads(path.read_text(encoding='utf-8'))
    change(value)
    write_json(path, value)


def config_error(s, token, *, requirement_id=None, **changes):
    function = api()
    arguments = dict(config_path=s.main, operation='infra', selection='all',
                     parameters=s.parameters, base_dir=s.root, interpreters=s.interpreters)
    arguments.update(changes)
    with pytest.raises(ValueError) as caught:
        function(**arguments)
    message = str(caught.value)
    assert token.lower() in message.lower() and 'infra' in message.lower()
    if requirement_id is not None:
        assert requirement_id in message
    assert events(s) == []


def cli_result(completed, code):
    actual_code = completed.returncode
    assert actual_code == code
    assert completed.stderr == b''
    assert completed.stdout.endswith(b'\n') and len(completed.stdout.splitlines()) == 1
    result = json.loads(completed.stdout)
    assert_shape(result)
    return result


def test_public_preparation_function_exists():
    api()


@pytest.mark.parametrize('operation,ids,tags', [
    ('infra', ['alpha', 'beta', 'all'], ['alpha-install', 'alpha-configure', 'beta-install', 'literal-all']),
    ('deps', ['vendor'], ['vendor-install', 'vendor-configure']),
])
def test_library_prepares_corresponding_document_and_complete_result(scenario, operation, ids, tags):
    result = invoke(scenario, operation)
    assert_success(scenario, result, operation, ids, tags)


@pytest.mark.parametrize('selection,ids,tags', [
    (['beta'], ['beta'], ['beta-install']),
    (['beta', 'alpha'], ['beta', 'alpha'],
     ['beta-install', 'alpha-install', 'alpha-configure']),
    (['all'], ['all'], ['literal-all']),
    ([], [], []),
])
def test_library_preserves_selection_order_and_literal_all(scenario, selection, ids, tags):
    result = invoke(scenario, selection=selection)
    assert_success(scenario, result, 'infra', ids, tags)


def test_empty_document_succeeds_without_effects(scenario):
    edit(scenario, 'infra', lambda doc: doc.update(requirements=[]))
    assert_success(scenario, invoke(scenario), 'infra', [], [])


@pytest.mark.parametrize('value,expected', [(0, '0'), (True, 'True'), (2.5, '2.5'), ('a b', 'a b')])
def test_library_supplies_selected_scalar_and_explicit_environment(scenario, value, expected):
    scenario.parameters['number'] = value
    result = invoke(scenario, selection=['beta'])
    assert result['status'] == 'succeeded'
    assert result['requirements'][0]['result']['commands'][0]['invocation']['env']['SCALAR'] == expected
    assert_events(scenario, ['beta-install'], scalar=expected)


def test_library_preserves_configurations_and_input_values(scenario):
    before_files = {p: p.read_bytes() for p in (scenario.main, scenario.infra, scenario.deps, scenario.values)}
    before_parameters = deepcopy(scenario.parameters)
    result = invoke(scenario, selection=['beta'])
    assert result['status'] == 'succeeded'
    assert scenario.parameters == before_parameters
    assert all(path.read_bytes() == raw for path, raw in before_files.items())


@pytest.mark.parametrize('selection,token', [(['missing-id'], 'missing-id'), ('wrong-selection', 'selection')])
def test_library_selection_error_precedes_effects(scenario, selection, token):
    config_error(scenario, token, selection=selection)


def test_library_unknown_operation_precedes_effects(scenario):
    function = api()
    with pytest.raises(ValueError) as caught:
        function(scenario.main, 'unmapped-operation', 'all', scenario.parameters,
                 base_dir=scenario.root, interpreters=scenario.interpreters)
    assert 'unmapped-operation' in str(caught.value)
    assert events(scenario) == []


@pytest.mark.parametrize('defect,token', [('commands', 'commands'), ('template', 'missing_value'), ('handler', 'missing_handler')])
def test_library_preflights_late_selected_chain_before_first_process(scenario, defect, token):
    def damage(doc):
        item = doc['requirements'][1]
        if defect == 'commands':
            item['commands'] = []
        elif defect == 'template':
            item['commands'][0]['argv'][4] = '${missing_value}'
        else:
            item['commands'][0]['interpreter']['name'] = 'missing_handler'
    edit(scenario, 'infra', damage)
    config_error(scenario, token, requirement_id='beta')


def test_library_ignores_unselected_chain_for_execution(scenario):
    edit(scenario, 'infra', lambda doc: doc['requirements'][1].update(commands=[]))
    result = invoke(scenario, selection=['alpha'])
    assert_success(scenario, result, 'infra', ['alpha'], ['alpha-install', 'alpha-configure'])


@pytest.mark.parametrize('case,token', [('parameter', 'token'), ('base', 'base_dir')])
def test_library_rejects_invalid_used_parameters_or_base(scenario, case, token):
    changes = {'base_dir': 'relative'} if case == 'base' else {'parameters': {**scenario.parameters, 'token': []}}
    config_error(scenario, token, **changes)


def test_library_accepts_configured_nonzero_process_success(scenario):
    def change(doc):
        command = doc['requirements'][1]['commands'][0]
        command['argv'][-1] = '7'
        command['interpreter']['options']['accept'] = [7]
    edit(scenario, 'infra', change)
    result = invoke(scenario, selection=['beta'])
    assert_success(scenario, result, 'infra', ['beta'], ['beta-install'], codes={'beta-install': 7})


def test_library_preserves_partial_work_and_stops_following_requirements(scenario):
    edit(scenario, 'infra', lambda doc: doc['requirements'][1]['commands'][0]['argv'].__setitem__(-1, '9'))
    result = invoke(scenario)
    assert_shape(result)
    assert result['status'] == 'failed' and result['operation'] == 'infra'
    assert [item['id'] for item in result['requirements']] == ['alpha', 'beta']
    assert result['requirements'][0]['result']['status'] == 'succeeded'
    failed = result['requirements'][1]['result']
    assert failed['status'] == 'failed' and failed['commands'][0]['exit_code'] == 9
    assert 'exit not accepted' in failed['error']
    assert all(token in result['error'] for token in ('infra', 'beta', 'exit not accepted'))
    assert_streams(result)
    assert_events(scenario, ['alpha-install', 'alpha-configure', 'beta-install'])


@pytest.mark.parametrize('kind', ['executable', 'cwd'])
def test_library_launch_failure_retains_earlier_requirement(scenario, kind):
    def change(doc):
        command = doc['requirements'][1]['commands'][0]
        if kind == 'executable':
            command['argv'][0] = str(scenario.root / 'missing-executable')
        else:
            command['cwd'] = 'missing-directory'
    edit(scenario, 'infra', change)
    result = invoke(scenario)
    assert_shape(result)
    assert result['status'] == 'failed'
    assert [item['id'] for item in result['requirements']] == ['alpha', 'beta']
    failed = result['requirements'][1]['result']['commands'][0]
    assert failed['exit_code'] is None and failed['stdout'] == failed['stderr'] == b''
    assert failed['interpretation'] is None and 'launch' in failed['error']
    assert all(token in result['error'] for token in ('infra', 'beta', 'missing-'))
    assert_events(scenario, ['alpha-install', 'alpha-configure'])


@pytest.mark.parametrize('interpreter,token', [('throwing', 'external interpreter refused'), ('malformed', 'success')])
def test_library_interpreter_failure_retains_raw_and_stops_chain(scenario, interpreter, token):
    scenario.interpreters['chosen'] = scenario.objects[interpreter]
    result = invoke(scenario)
    assert result['status'] == 'failed'
    assert [item['id'] for item in result['requirements']] == ['alpha']
    commands = result['requirements'][0]['result']['commands']
    assert len(commands) == 1 and token in commands[0]['error']
    assert_streams(result)
    assert_events(scenario, ['alpha-install'])


def test_library_retains_opaque_value_without_cli_restriction(scenario):
    scenario.interpreters['chosen'] = scenario.objects['opaque']
    result = invoke(scenario, selection=['beta'])
    assert result['status'] == 'succeeded'
    assert result['requirements'][0]['result']['commands'][0]['interpretation']['value'] == b'opaque\x00\xff'


def test_library_keeps_empty_streams_as_complete_bytes(scenario):
    empty = scenario.root / 'empty.hex'
    empty.write_text('', encoding='utf-8')
    scenario.parameters.update(stdout_file=str(empty), stderr_file=str(empty))
    result = invoke(scenario, selection=['beta'])
    assert_shape(result)
    assert result['status'] == 'succeeded' and result['error'] is None
    assert [item['id'] for item in result['requirements']] == ['beta']
    assert len(result['requirements'][0]['result']['commands']) == 1
    assert_streams(result, stdout=b'', stderr=b'')
    assert_events(scenario, ['beta-install'])


def test_library_retains_complete_long_distinct_binary_streams(scenario):
    scenario.parameters.update(stdout_file=str(FIXTURES / 'long-stdout.hex'),
                               stderr_file=str(FIXTURES / 'long-stderr.hex'))
    result = invoke(scenario, selection=['beta'])
    assert_shape(result)
    assert result['status'] == 'succeeded' and result['error'] is None
    assert [item['id'] for item in result['requirements']] == ['beta']
    assert len(result['requirements'][0]['result']['commands']) == 1
    assert_streams(result, stdout=payload('long-stdout.hex'), stderr=payload('long-stderr.hex'))
    assert_events(scenario, ['beta-install'])


@pytest.mark.parametrize('operation,ids,tags', [
    ('infra', ['alpha', 'beta', 'all'], ['alpha-install', 'alpha-configure', 'beta-install', 'literal-all']),
    ('deps', ['vendor'], ['vendor-install', 'vendor-configure']),
])
def test_cli_real_entry_prepares_selected_document_from_foreign_cwd(scenario, operation, ids, tags):
    result = cli_result(run_cli(scenario, operation), 0)
    assert_success(scenario, result, operation, ids, tags, encoded=True)


@pytest.mark.parametrize('selection,ids,tags', [([], [], []), (['all'], ['all'], ['literal-all']),
    (['beta', 'alpha'], ['beta', 'alpha'], ['beta-install', 'alpha-install', 'alpha-configure'])])
def test_cli_transports_selection_without_reinterpreting_it(scenario, selection, ids, tags):
    result = cli_result(run_cli(scenario, selection=selection), 0)
    assert_success(scenario, result, 'infra', ids, tags, encoded=True)


def test_cli_empty_configuration_has_empty_success(scenario):
    edit(scenario, 'deps', lambda doc: doc.update(requirements=[]))
    result = cli_result(run_cli(scenario, 'deps'), 0)
    assert_success(scenario, result, 'deps', [], [], encoded=True)


def test_cli_loads_replacement_interpreter_from_configuration(scenario):
    edit(scenario, 'main', lambda doc: doc['interpreters']['chosen'].update(attribute='byte_result'))
    result = cli_result(run_cli(scenario, selection=['beta']), 0)
    answer = result['requirements'][0]['result']['commands'][0]['interpretation']
    assert answer == dict(success=True, value=['bytes', False, 0], error=None, selected='bytes')
    assert type(answer['value'][1]) is bool and type(answer['value'][2]) is int
    assert_streams(result, encoded=True)
    assert_events(scenario, ['beta-install'])


def test_cli_keeps_empty_streams_in_explicit_encoding(scenario):
    empty = scenario.root / 'empty.hex'
    empty.write_text('', encoding='utf-8')
    scenario.parameters.update(stdout_file=str(empty), stderr_file=str(empty))
    write_json(scenario.values, scenario.parameters)
    result = cli_result(run_cli(scenario, selection=['beta']), 0)
    record = result['requirements'][0]['result']['commands'][0]
    assert record['stdout'] == record['stderr'] == dict(encoding='base64', data='')
    assert_events(scenario, ['beta-install'])


def test_cli_preserves_partial_failure_and_returns_one(scenario):
    edit(scenario, 'infra', lambda doc: doc['requirements'][0]['commands'][1]['argv'].__setitem__(-1, '9'))
    result = cli_result(run_cli(scenario), 1)
    assert result['status'] == 'failed' and result['operation'] == 'infra'
    assert [item['id'] for item in result['requirements']] == ['alpha']
    commands = result['requirements'][0]['result']['commands']
    assert [record['exit_code'] for record in commands] == [0, 9]
    assert all(token in result['error'] for token in ('infra', 'alpha', 'exit not accepted'))
    assert_streams(result, encoded=True)
    assert_events(scenario, ['alpha-install', 'alpha-configure'])


def test_cli_accepts_interpreter_confirmed_nonzero_exit(scenario):
    def change(doc):
        command = doc['requirements'][1]['commands'][0]
        command['argv'][-1] = '7'
        command['interpreter']['options']['accept'] = [7]
    edit(scenario, 'infra', change)
    result = cli_result(run_cli(scenario, selection=['beta']), 0)
    assert_success(scenario, result, 'infra', ['beta'], ['beta-install'], encoded=True, codes={'beta-install': 7})


def test_cli_retains_complete_long_binary_streams(scenario):
    scenario.parameters.update(stdout_file=str(FIXTURES / 'long-stdout.hex'),
                               stderr_file=str(FIXTURES / 'long-stderr.hex'))
    write_json(scenario.values, scenario.parameters)
    result = cli_result(run_cli(scenario, selection=['beta']), 0)
    assert_streams(result, encoded=True, stdout=payload('long-stdout.hex'), stderr=payload('long-stderr.hex'))
    assert_events(scenario, ['beta-install'])


@pytest.mark.parametrize('attribute,token', [('throwing', 'external interpreter refused'), ('malformed', 'success')])
def test_cli_interpreter_errors_keep_raw_and_partial_effects(scenario, attribute, token):
    edit(scenario, 'main', lambda doc: doc['interpreters']['chosen'].update(attribute=attribute))
    result = cli_result(run_cli(scenario), 1)
    assert result['status'] == 'failed'
    assert [item['id'] for item in result['requirements']] == ['alpha']
    commands = result['requirements'][0]['result']['commands']
    assert len(commands) == 1 and token in commands[0]['error']
    assert_streams(result, encoded=True)
    assert_events(scenario, ['alpha-install'])


def test_cli_launch_failure_preserves_nullable_code_and_empty_raw(scenario):
    edit(scenario, 'infra', lambda doc: doc['requirements'][1]['commands'][0].update(cwd='missing-directory'))
    result = cli_result(run_cli(scenario), 1)
    assert result['status'] == 'failed'
    assert [item['id'] for item in result['requirements']] == ['alpha', 'beta']
    record = result['requirements'][1]['result']['commands'][0]
    assert record['exit_code'] is None and record['interpretation'] is None
    assert record['stdout'] == record['stderr'] == dict(encoding='base64', data='')
    assert 'missing-directory' in record['error']
    assert_events(scenario, ['alpha-install', 'alpha-configure'])


@pytest.mark.parametrize('attribute', ['opaque', 'integer_key', 'tuple_value', 'not_a_number', 'infinity'])
def test_cli_rejects_non_json_interpretation_before_losing_raw_result(scenario, attribute):
    edit(scenario, 'main', lambda doc: doc['interpreters']['chosen'].update(attribute=attribute))
    result = cli_result(run_cli(scenario), 1)
    assert result['status'] == 'failed'
    assert [item['id'] for item in result['requirements']] == ['alpha']
    commands = result['requirements'][0]['result']['commands']
    assert len(commands) == 1 and commands[0]['interpretation'] is None
    assert commands[0]['error'] and 'chosen' in commands[0]['error']
    assert_streams(result, encoded=True)
    assert_events(scenario, ['alpha-install'])


@pytest.mark.parametrize('field,value,token', [
    ('module', 'missing_env2_plugin', 'missing_env2_plugin'),
    ('attribute', 'missing_attribute', 'missing_attribute'),
    ('attribute', 'not_interpreter', 'chosen'),
])
def test_cli_loading_errors_precede_external_effects(scenario, field, value, token):
    edit(scenario, 'main', lambda doc: doc['interpreters']['chosen'].__setitem__(field, value))
    completed = run_cli(scenario)
    code = completed.returncode
    assert code == 2 and completed.stdout == b''
    message = completed.stderr.decode('utf-8')
    assert token in message and 'chosen' in message
    assert_events(scenario, [])


@pytest.mark.parametrize('case,token', [
    ('missing-file', 'app.json'), ('bad-json', 'values.json'),
    ('relative-base', 'base'), ('bad-selection', 'requirements'), ('missing-argument', '--config'),
    ('bad-parameter', 'token'), ('late-template', 'missing_value'),
])
def test_cli_input_errors_have_context_and_no_process_effects(scenario, case, token):
    arguments = ['infra', '--config', str(scenario.main), '--parameters', str(scenario.values),
                 '--base-dir', str(scenario.root), '--requirements', 'all']
    if case == 'missing-file':
        scenario.main.unlink()
    elif case == 'bad-json':
        scenario.values.write_text('{', encoding='utf-8')
    elif case == 'unknown-id':
        arguments[-1] = '["missing-id"]'
    elif case == 'relative-base':
        arguments[-3] = 'relative-base'
    elif case == 'bad-selection':
        arguments[-1] = 'not-an-array'
    elif case == 'missing-argument':
        del arguments[1:3]
    elif case == 'bad-parameter':
        write_json(scenario.values, {**scenario.parameters, 'token': []})
    else:
        edit(scenario, 'infra', lambda doc: doc['requirements'][1]['commands'][0]['argv'].__setitem__(4, '${missing_value}'))
    completed = run_cli(scenario, arguments=arguments)
    code = completed.returncode
    assert code == 2 and completed.stdout == b''
    message = completed.stderr.decode('utf-8').lower()
    contexts = ('requirements', 'selection') if case == 'bad-selection' else (token.lower(),)
    assert any(context in message for context in contexts)
    if case == 'late-template':
        assert 'infra' in message and 'beta' in message
    assert_events(scenario, [])


def test_cli_does_not_modify_any_configuration(scenario):
    paths = (scenario.main, scenario.infra, scenario.deps, scenario.values)
    before = {path: path.read_bytes() for path in paths}
    cli_result(run_cli(scenario, 'deps'), 0)
    assert all(path.read_bytes() == raw for path, raw in before.items())
