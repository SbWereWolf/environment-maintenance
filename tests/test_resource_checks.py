"""Real configured checks, independent state/trace oracles and explicit CLI boundaries."""
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
FIXTURES = ROOT / 'tests/fixtures/resource-checking'
TOOL = ROOT / 'examples/resource-checking/check_settings.py'


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def probe_command(tag, resource):
    command = fixture('probe-command.json')
    command['argv'][4] = tag
    command['argv'][5] = '${' + resource + '}'
    return command


def action(tag, mode, resource):
    command = fixture('tool-command.json')
    if mode == 'consistency':
        command['argv'] += ['consistency', '--config', '${settings}', '--operation', '${operation}',
            '--writer', '${writer}', '--reader', '${reader}', '--queue-variable', '${variable}']
    else:
        command['argv'] += [mode, '--path', '${' + resource + '}']
    return dict(commands=[probe_command(tag, resource), command, probe_command(tag + '-tail', resource)])


def resource(identifier, tag, key, *, available):
    checks = dict(presence=action(tag + '-presence', 'presence', key))
    if available:
        checks['availability'] = action(tag + '-availability', 'availability', key)
    return dict(id=identifier, commands=[probe_command('INSTALL-' + tag, key)], checks=checks,
                owner=dict(keep=[False, 0, 'unchanged']))


def remember(s):
    s.original = {p: p.read_bytes() if p.exists() else None for p in s.inputs}


def save_doc(s, operation, document):
    write_json(s.documents[operation], document)
    remember(s)


def document(s, operation):
    return json.loads(s.documents[operation].read_text())


def parameters(s, **changes):
    s.parameters.update(changes)
    write_json(s.values, s.parameters)
    remember(s)


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    root = tmp_path / 'serviced application with spaces'
    root.mkdir()
    config = tmp_path / 'descriptions'
    config.mkdir()
    plugins = tmp_path / 'external plugins'
    plugins.mkdir()
    shutil.copyfile(FIXTURES / 'plugins.py', plugins / 'env2_check_plugins.py')
    main = config / 'main.json'
    shutil.copyfile(FIXTURES / 'main.json', main)
    for name, target in (('settings-main.json', 'settings.json'), ('settings-before.json', 'infra-one.json'),
                         ('other-resource.json', 'infra-two.json'), ('dependency.json', 'deps-one.json')):
        shutil.copyfile(FIXTURES / name, root / target)
    documents = {op: config / (op + '.json') for op in ('infra', 'deps', 'check')}
    write_json(documents['infra'], dict(requirements=[
        resource('service', 'infra-service', 'infra_one', available=True),
        resource('later', 'infra-later', 'infra_two', available=False)]))
    write_json(documents['deps'], dict(requirements=[
        resource('service', 'deps-service', 'deps_one', available=True)]))
    write_json(documents['check'], dict(requirements=[
        dict(id='agreement', **action('check-agreement', 'consistency', 'infra_one')),
        dict(id='after', **action('check-after', 'availability', 'deps_one'))]))
    values = config / 'values.json'
    selected = fixture('parameters.json')
    selected.update(python=sys.executable, source_path=str(ROOT / 'src'), tool=str(TOOL),
        probe=str(FIXTURES / 'probe.py'), events=str(root / 'events.jsonl'),
        infra_one=str(root / 'infra-one.json'), infra_two=str(root / 'infra-two.json'),
        deps_one=str(root / 'deps-one.json'), settings=str(root / 'settings.json'),
        stdout_file=str(FIXTURES / 'stdout.hex'), stderr_file=str(FIXTURES / 'stderr.hex'))
    write_json(values, selected)
    objects = runpy.run_path(str(FIXTURES / 'plugins.py'))
    s = SimpleNamespace(root=root, main=main, documents=documents, parameters=selected,
        values=values, plugins=plugins, events=root / 'events.jsonl', foreign_cwd=tmp_path,
        registry={'result': objects['exit_result'], 'opaque': objects['opaque_result']},
        settings=root / 'settings.json', target=root / 'infra-one.json')
    s.inputs = [main, values, *documents.values(), s.settings, s.target,
                root / 'infra-two.json', root / 'deps-one.json']
    remember(s)
    monkeypatch.setenv('ENV2_HOST_ONLY', 'must not reach command env')
    return s


def api():
    function = getattr(public_api, 'check_resources', None)
    assert callable(function), 'Missing required public resource checking API'
    return function


def invoke(s, **changes):
    arguments = dict(config_path=s.main, parameters=s.parameters,
                     base_dir=s.root, interpreters=s.registry)
    arguments.update(changes)
    return api()(**arguments)


def cli(s, *, omit=None, base_dir=None, extra=()):
    pairs = [('--config', str(s.main)), ('--parameters', str(s.values)),
             ('--base-dir', str(s.root if base_dir is None else base_dir))]
    argv = [sys.executable, '-B', '-m', 'environment_maintenance', 'check']
    for flag, value in pairs:
        if flag != omit:
            argv += [flag, value]
    argv += list(extra)
    return subprocess.run(argv, cwd=s.foreign_cwd, capture_output=True,
        env=dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / 'src'), str(s.plugins)))))


def require_tool():
    assert TOOL.is_file(), 'Missing required real resource checking tool'


def tool(s, mode, *, path=None, variable='CHANNEL', reader='sink'):
    require_tool()
    argv = [sys.executable, '-B', str(TOOL), mode]
    if mode == 'consistency':
        argv += ['--config', str(s.settings), '--operation', 'applications', '--writer', 'source',
                 '--reader', reader, '--queue-variable', variable]
    else:
        argv += ['--path', str(s.target if path is None else path)]
    return subprocess.run(argv, cwd=s.foreign_cwd, capture_output=True,
        env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')))


def preserved(s):
    for path, before in s.original.items():
        if before is None:
            assert not path.exists()
        else:
            assert path.read_bytes() == before


def no_effects(s):
    assert not s.events.exists()
    preserved(s)


def empty(s):
    for operation in ('infra', 'deps', 'check'):
        save_doc(s, operation, dict(requirements=[]))


def decode(command, field, encoded):
    value = command[field]
    if encoded:
        assert set(value) == {'encoding', 'data'} and value['encoding'] == 'base64'
        value = base64.b64decode(value['data'], validate=True)
    assert type(value) is bytes
    return value


def shape(result):
    shapes = fixture('shapes.json')
    assert set(result) == set(shapes['aggregate'])
    assert result['operation'] == 'check'
    for row in result['resources']:
        assert set(row) == set(shapes['resource'])
        assert set(row['availability']) == set(shapes['availability'])
        assert set(row['presence']) == set(shapes['action'])
    for row in result['checks']:
        assert set(row) == set(shapes['extra']) and set(row['result']) == set(shapes['action'])


def source_rows(rows):
    actual = [{key: row[key] for key in ('operation', 'id')} for row in rows]
    assert canonical(actual) == canonical(fixture('sources.json'))


def unconfigured_availability(value):
    assert value == dict(status='not_configured', result=None, reason=None)


def skipped_availability(value):
    assert value == dict(status='not_attempted', result=None, reason='presence_failed')


def expected_labels(s, tag):
    base = tag.removesuffix('-tail')
    key = fixture('trace-resources.json')[base]
    return dict(PYTHON=sys.executable, PROBE=str(FIXTURES / 'probe.py'), EVENTS=str(s.events),
        TAG=tag, RESOURCE=s.parameters[key], STDOUT=str(FIXTURES / 'stdout.hex'),
        STDERR=str(FIXTURES / 'stderr.hex'), TOOL=str(TOOL), SETTINGS=str(s.settings))


def command_shape(s, command):
    assert set(command) == set(fixture('shapes.json')['command'])
    assert set(command['invocation']) == {'argv', 'cwd', 'env'}
    assert command['invocation']['cwd'] == str(s.root)
    assert command['interpreter']['name'] == 'result'


def probe_result(s, command, tag, encoded, *, code=0):
    command_shape(s, command)
    labels = expected_labels(s, tag)
    expected = [labels.get(value, value) for value in fixture('expected-probe-argv.json')]
    expected[-1] = str(code)
    assert command['invocation']['argv'] == expected
    assert command['invocation']['env'] == dict(RESOURCE_TOKEN='selected choice', NUMBER='42')
    assert decode(command, 'stdout', encoded) == bytes.fromhex((FIXTURES / 'stdout.hex').read_text())
    assert decode(command, 'stderr', encoded) == bytes.fromhex((FIXTURES / 'stderr.hex').read_text())
    assert type(command['exit_code']) is int and command['exit_code'] == code
    assert command['error'] is None
    assert command['interpretation'] == dict(success=True, value=code, error=None)
    assert type(command['interpretation']['value']) is int


def successful_action(s, value, tag, mode, encoded, *, first_code=0):
    assert set(value) == set(fixture('shapes.json')['action'])
    assert value['status'] == 'succeeded' and value['error'] is None
    assert len(value['commands']) == 3
    first, middle, last = value['commands']
    probe_result(s, first, tag, encoded, code=first_code)
    probe_result(s, last, tag + '-tail', encoded)
    command_shape(s, middle)
    labels = expected_labels(s, tag)
    expected = [labels.get(part, part) for part in fixture('expected-tool-argv.json')[mode]]
    assert middle['invocation']['argv'] == expected
    assert middle['invocation']['env'] == {'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
    assert type(middle['exit_code']) is int and middle['exit_code'] == 0
    assert middle['error'] is None
    assert middle['interpretation'] == dict(success=True, value=0, error=None)
    assert type(middle['interpretation']['value']) is int
    raw = decode(middle, 'stdout', encoded)
    assert raw.endswith(b'\n') and len(raw.splitlines()) == 1
    expected_answer = fixture('tool-success.json') if mode == 'consistency' else dict(status='succeeded', check=mode)
    assert canonical(json.loads(raw)) == canonical(expected_answer)
    assert decode(middle, 'stderr', encoded) == b''


def trace_matches(s, name, *, absent_first=False):
    actual = [json.loads(line) for line in s.events.read_text().splitlines()]
    tags = fixture('traces.json')[name]
    assert [row['tag'] for row in actual] == tags
    expected = []
    for tag in tags:
        row = fixture('event.json')
        row.update(tag=tag, cwd=str(s.root))
        if absent_first and (tag.startswith('infra-service') or tag.startswith('check-agreement')):
            row['exists'] = False
        expected.append(row)
    assert canonical(actual) == canonical(expected)


def cli_json(process, *, code=0):
    assert process.returncode == code, 'Missing required configured resource checking CLI'
    assert process.stderr == b''
    assert process.stdout.endswith(b'\n') and len(process.stdout.splitlines()) == 1
    return json.loads(process.stdout)


def success(s, result, *, encoded, first_absent=False, first_code=0):
    shape(result)
    assert result['status'] == 'succeeded' and result['error'] is None
    source_rows(result['resources'])
    for index, (row, tag) in enumerate(zip(result['resources'], ('infra-service', 'infra-later', 'deps-service'))):
        successful_action(s, row['presence'], tag + '-presence', 'presence', encoded,
                          first_code=first_code if index == 0 else 0)
        available = row['availability']
        if index == 1 or (index == 0 and first_absent):
            unconfigured_availability(available)
        else:
            assert available['status'] == 'succeeded' and available['reason'] is None
            successful_action(s, available['result'], tag + '-availability', 'availability', encoded)
    assert [r['id'] for r in result['checks']] == ['agreement', 'after']
    successful_action(s, result['checks'][0]['result'], 'check-agreement', 'consistency', encoded)
    successful_action(s, result['checks'][1]['result'], 'check-after', 'availability', encoded)
    trace_matches(s, 'availability-absent' if first_absent else 'success')
    preserved(s)


def failed_action(s, value, tag, cause):
    assert value['status'] == 'failed' and value['error']
    assert len(value['commands']) == 2
    probe_result(s, value['commands'][0], tag, True)
    command = value['commands'][1]
    command_shape(s, command)
    assert type(command['exit_code']) is int and command['exit_code'] == 1
    assert command['interpretation'] == dict(success=False, value=1, error='external check failed')
    assert type(command['interpretation']['value']) is int
    assert command['error'] and decode(command, 'stdout', True) == b''
    assert cause.lower() in decode(command, 'stderr', True).decode().lower()


def remaining_success(s, result):
    source_rows(result['resources'])
    successful_action(s, result['resources'][1]['presence'], 'infra-later-presence', 'presence', True)
    unconfigured_availability(result['resources'][1]['availability'])
    successful_action(s, result['resources'][2]['presence'], 'deps-service-presence', 'presence', True)
    assert result['resources'][2]['availability']['status'] == 'succeeded'
    assert result['resources'][2]['availability']['reason'] is None
    successful_action(s, result['resources'][2]['availability']['result'], 'deps-service-availability', 'availability', True)
    assert [r['id'] for r in result['checks']] == ['agreement', 'after']
    successful_action(s, result['checks'][1]['result'], 'check-after', 'availability', True)


def test_cli_checks_all_sources_and_real_conditions(scenario):
    success(scenario, cli_json(cli(scenario)), encoded=True)


def test_public_check_api_preserves_full_bytes_and_context(scenario):
    success(scenario, invoke(scenario), encoded=False)


def test_public_check_api_preserves_opaque_interpretation(scenario):
    selected = document(scenario, 'infra')
    selected['requirements'][0]['checks']['presence']['commands'][0]['interpreter']['name'] = 'opaque'
    save_doc(scenario, 'infra', selected)
    result = invoke(scenario)
    shape(result)
    assert result['status'] == 'succeeded' and result['error'] is None
    command = result['resources'][0]['presence']['commands'][0]
    assert type(command['interpretation']['value']) is bytes
    assert command['interpretation']['value'] == bytes.fromhex((FIXTURES / 'stdout.hex').read_text())
    assert decode(command, 'stdout', False) == command['interpretation']['value']
    assert decode(command, 'stderr', False) == bytes.fromhex((FIXTURES / 'stderr.hex').read_text())
    trace_matches(scenario, 'success')
    preserved(scenario)


def test_failed_presence_skips_availability_but_continues_independent_checks(scenario):
    scenario.target.unlink()
    remember(scenario)
    result = cli_json(cli(scenario), code=1)
    shape(result)
    assert result['status'] == 'failed'
    assert all(part in result['error'].lower() for part in ('infra', 'service', 'presence'))
    row = result['resources'][0]
    failed_action(scenario, row['presence'], 'infra-service-presence', 'infra-one.json')
    skipped_availability(row['availability'])
    remaining_success(scenario, result)
    failed_action(scenario, result['checks'][0]['result'], 'check-agreement', 'infra-one.json')
    trace_matches(scenario, 'presence-failed', absent_first=True)
    preserved(scenario)


def test_failed_availability_keeps_other_results(scenario):
    scenario.target.write_text('[]')
    remember(scenario)
    result = cli_json(cli(scenario), code=1)
    shape(result)
    assert result['status'] == 'failed'
    assert all(part in result['error'].lower() for part in ('infra', 'service', 'availability'))
    successful_action(scenario, result['resources'][0]['presence'], 'infra-service-presence', 'presence', True)
    failed_action(scenario, result['resources'][0]['availability']['result'], 'infra-service-availability', 'object')
    assert result['resources'][0]['availability']['status'] == 'failed'
    assert result['resources'][0]['availability']['reason'] is None
    remaining_success(scenario, result)
    failed_action(scenario, result['checks'][0]['result'], 'check-agreement', 'object')
    trace_matches(scenario, 'availability-failed')
    preserved(scenario)


def test_failed_extra_stops_its_chain_but_not_next_extra(scenario):
    selected = json.loads(scenario.target.read_text())
    selected['requirements'][2]['commands'][0]['env']['CHANNEL'] = 'different.jobs'
    write_json(scenario.target, selected)
    remember(scenario)
    result = cli_json(cli(scenario), code=1)
    shape(result)
    assert result['status'] == 'failed' and all(p in result['error'].lower() for p in ('check', 'agreement'))
    for row, tag in zip(result['resources'], ('infra-service', 'infra-later', 'deps-service')):
        successful_action(scenario, row['presence'], tag + '-presence', 'presence', True)
        if tag == 'infra-later':
            unconfigured_availability(row['availability'])
        else:
            assert row['availability']['status'] == 'succeeded' and row['availability']['reason'] is None
            successful_action(scenario, row['availability']['result'], tag + '-availability', 'availability', True)
    failed_action(scenario, result['checks'][0]['result'], 'check-agreement', 'CHANNEL')
    successful_action(scenario, result['checks'][1]['result'], 'check-after', 'availability', True)
    trace_matches(scenario, 'extra-failed')
    preserved(scenario)


def test_unconfigured_availability_is_not_claimed_successful(scenario):
    selected = document(scenario, 'infra')
    del selected['requirements'][0]['checks']['availability']
    save_doc(scenario, 'infra', selected)
    success(scenario, cli_json(cli(scenario)), encoded=True, first_absent=True)


def test_unconfigured_availability_stays_unconfigured_after_failed_presence(scenario):
    selected = document(scenario, 'infra')
    del selected['requirements'][0]['checks']['availability']
    save_doc(scenario, 'infra', selected)
    scenario.target.unlink()
    remember(scenario)
    result = cli_json(cli(scenario), code=1)
    shape(result)
    assert result['status'] == 'failed'
    assert result['resources'][0]['presence']['status'] == 'failed'
    unconfigured_availability(result['resources'][0]['availability'])
    remaining_success(scenario, result)
    trace_matches(scenario, 'presence-failed', absent_first=True)
    preserved(scenario)


def test_empty_configurations_have_explicit_empty_success(scenario):
    empty(scenario)
    result = cli_json(cli(scenario))
    assert result == dict(operation='check', status='succeeded', resources=[], checks=[], error=None)
    no_effects(scenario)


@pytest.mark.parametrize('invalid', ['api-base', 'api-parameters', 'api-interpreters',
                                     'cli-base', 'cli-parameters', 'cli-plugin'])
def test_empty_selection_still_validates_common_inputs(scenario, invalid):
    empty(scenario)
    if invalid.startswith('api-'):
        function = api()
        changes = {'api-base': dict(base_dir='relative'),
            'api-parameters': dict(parameters={'bad': []}), 'api-interpreters': dict(interpreters=[])}[invalid]
        arguments = dict(config_path=scenario.main, parameters=scenario.parameters,
                         base_dir=scenario.root, interpreters=scenario.registry)
        arguments.update(changes)
        with pytest.raises(ValueError) as caught:
            function(**arguments)
        cause = str(caught.value).lower()
    else:
        options = {}
        if invalid == 'cli-base':
            options['base_dir'] = 'relative'
        elif invalid == 'cli-parameters':
            parameters(scenario, bad=[])
        else:
            selected = json.loads(scenario.main.read_text())
            selected['interpreters']['result']['attribute'] = '__doc__'
            write_json(scenario.main, selected)
            remember(scenario)
        process = cli(scenario, **options)
        assert process.returncode == 2 and process.stdout == b''
        cause = process.stderr.decode().splitlines()[-1].lower()
    required = 'base' if invalid.endswith('base') else 'scalar' if invalid.endswith('parameters') else 'interpret'
    assert required in cause, 'Wrong common-input failure cause'
    no_effects(scenario)


def late_number(s, literal):
    selected = document(s, 'check')
    selected['requirements'][1]['commands'][1]['interpreter']['options']['late_number'] = 0
    raw = json.dumps(selected)
    assert raw.count('"late_number": 0') == 1
    s.documents['check'].write_text(raw.replace('"late_number": 0', '"late_number": ' + literal))
    remember(s)


@pytest.mark.parametrize('invalid', ['presence', 'availability', 'template', 'interpreter', 'json'])
def test_all_declared_plans_are_validated_before_any_process(scenario, invalid):
    if invalid == 'json':
        late_number(scenario, '1e400')
        process = cli(scenario)
        assert process.returncode == 2 and process.stdout == b''
        assert 'json' in process.stderr.decode().splitlines()[-1].lower(), 'Wrong JSON preflight cause'
    else:
        operation = 'infra' if invalid in ('presence', 'availability') else 'check'
        selected = document(scenario, operation)
        if invalid == 'presence':
            del selected['requirements'][0]['checks']['presence']
        elif invalid == 'availability':
            selected['requirements'][0]['checks']['availability']['commands'] = []
            scenario.target.unlink()
        elif invalid == 'template':
            selected['requirements'][1]['commands'][1]['argv'][2] = '${missing_tool}'
        else:
            selected['requirements'][1]['commands'][1]['interpreter']['name'] = 'unknown'
        save_doc(scenario, operation, selected)
        with pytest.raises(ValueError) as caught:
            invoke(scenario)
        cause = str(caught.value).lower()
        expected = 'missing_tool' if invalid == 'template' else 'unknown' if invalid == 'interpreter' else invalid
        assert operation in cause and expected in cause, 'Wrong selected-plan failure context'
    no_effects(scenario)


def test_finite_late_json_metadata_is_preserved(scenario):
    late_number(scenario, '1e300')
    result = cli_json(cli(scenario))
    success(scenario, result, encoded=True)
    options = result['checks'][1]['result']['commands'][1]['interpreter']['options']
    assert options['late_number'] == 1e300


@pytest.mark.parametrize('flag', ['--config', '--parameters', '--base-dir'])
def test_configured_check_requires_each_working_argument(scenario, flag):
    process = cli(scenario, omit=flag)
    assert process.returncode == 2 and process.stdout == b''
    cause = process.stderr.decode().splitlines()[-1]
    assert flag in cause and 'check' in cause, 'Wrong required checking argument cause'
    no_effects(scenario)




@pytest.mark.parametrize('arguments', [('--values', 'unused.json'), ('--set', 'unused=value'),
                                     ('--dry-run',), ('--requirements', 'all')])
def test_configured_check_reports_foreign_flags(scenario, arguments):
    process = cli(scenario, extra=arguments)
    assert process.returncode == 0, process.stderr
    assert arguments[0].encode() in process.stderr
    success(scenario, json.loads(process.stdout), encoded=True)




@pytest.mark.parametrize('operation', ['infra', 'deps', 'check'])
def test_each_resource_source_mapping_is_required_before_effects(scenario, operation):
    selected = json.loads(scenario.main.read_text())
    del selected['operations'][operation]
    write_json(scenario.main, selected)
    remember(scenario)
    with pytest.raises(ValueError) as caught:
        invoke(scenario)
    assert operation in str(caught.value)
    no_effects(scenario)


@pytest.mark.parametrize('mode', ['presence', 'availability', 'consistency'])
def test_real_external_tool_confirms_selected_resource_state(scenario, mode):
    process = tool(scenario, mode, variable='OTHER_CHANNEL')
    assert process.returncode == 0 and process.stderr == b''
    assert process.stdout.endswith(b'\n') and len(process.stdout.splitlines()) == 1
    expected = fixture('tool-success-other.json') if mode == 'consistency' else dict(status='succeeded', check=mode)
    assert canonical(json.loads(process.stdout)) == canonical(expected)
    no_effects(scenario)


def test_real_consistency_rejects_unequal_selected_strings(scenario):
    selected = json.loads(scenario.target.read_text())
    selected['requirements'][2]['commands'][0]['env']['CHANNEL'] = 'different.jobs'
    write_json(scenario.target, selected)
    remember(scenario)
    process = tool(scenario, 'consistency')
    assert process.returncode == 1 and process.stdout == b''
    cause = process.stderr.decode()
    assert all(part in cause for part in ('source', 'sink', 'CHANNEL'))
    no_effects(scenario)


def test_real_availability_rejects_an_unusable_existing_file(scenario):
    scenario.target.write_text('[]')
    remember(scenario)
    process = tool(scenario, 'availability')
    assert process.returncode == 1 and process.stdout == b''
    assert 'object' in process.stderr.decode().lower()
    no_effects(scenario)


def test_real_presence_reports_an_absent_file(scenario):
    selected = scenario.root / 'missing.json'
    process = tool(scenario, 'presence', path=selected)
    assert process.returncode == 1 and process.stdout == b''
    assert 'missing.json' in process.stderr.decode()
    assert not selected.exists()
    no_effects(scenario)


def test_real_consistency_reports_unknown_selected_id(scenario):
    process = tool(scenario, 'consistency', reader='unknown-reader')
    assert process.returncode == 1 and process.stdout == b''
    assert 'unknown-reader' in process.stderr.decode()
    no_effects(scenario)


def test_cli_retains_raw_result_when_interpreter_answer_is_not_json(scenario):
    selected = document(scenario, 'infra')
    selected['requirements'][0]['checks']['presence']['commands'][0]['interpreter']['name'] = 'opaque'
    save_doc(scenario, 'infra', selected)
    result = cli_json(cli(scenario), code=1)
    shape(result)
    assert result['status'] == 'failed' and result['error']
    row = result['resources'][0]
    assert row['presence']['status'] == 'failed' and len(row['presence']['commands']) == 1
    command = row['presence']['commands'][0]
    assert command['exit_code'] == 0 and command['interpretation'] is None
    assert 'bytes' in command['error'].lower()
    assert decode(command, 'stdout', True) == bytes.fromhex((FIXTURES / 'stdout.hex').read_text())
    assert decode(command, 'stderr', True) == bytes.fromhex((FIXTURES / 'stderr.hex').read_text())
    skipped_availability(row['availability'])
    remaining_success(scenario, result)
    successful_action(scenario, result['checks'][0]['result'], 'check-agreement', 'consistency', True)
    trace_matches(scenario, 'plugin-failed')
    preserved(scenario)


def test_configured_interpretation_can_accept_a_real_nonzero_check_exit(scenario):
    selected = document(scenario, 'infra')
    command = selected['requirements'][0]['checks']['presence']['commands'][0]
    command['argv'][-1] = '3'
    command['interpreter']['options']['accept'] = [3]
    save_doc(scenario, 'infra', selected)
    result = cli_json(cli(scenario))
    success(scenario, result, encoded=True, first_code=3)


@pytest.mark.parametrize('values', fixture('invalid-values.json'), ids=lambda row: row['case'])
def test_real_consistency_requires_two_nonempty_strings(scenario, values):
    selected = json.loads(scenario.target.read_text())
    selected['requirements'][0]['commands'][0]['env']['CHANNEL'] = values['left']
    selected['requirements'][2]['commands'][0]['env']['CHANNEL'] = values['right']
    write_json(scenario.target, selected)
    remember(scenario)
    process = tool(scenario, 'consistency')
    assert process.returncode == 1 and process.stdout == b''
    cause = process.stderr.decode().lower()
    assert 'source' in cause and 'channel' in cause
    assert 'string' in cause and 'empty' in cause
    no_effects(scenario)
