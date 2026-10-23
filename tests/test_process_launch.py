"""Configured run, full external results and real independently controlled Linux consoles."""
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
from process_launch_support import ConsoleLab, terminal_argv, visible_server, wait_for


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/process-launch'
TOOL = ROOT / 'examples/process-launch/start_console.py'


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def payload(name):
    return bytes.fromhex((FIXTURES / (name + '.hex')).read_text())


def command(argv, *, interpreter='result', accept=(0,), env=None):
    return dict(argv=argv, cwd='.', env={} if env is None else env,
        interpreter=dict(name=interpreter, options=dict(accept=list(accept))))


def probe(s, label, *, code=0, interpreter='result', accept=(0,)):
    return command(['${python}', '-B', str(FIXTURES / 'probe.py'), '${directory}', label,
        str(FIXTURES / 'stdout.hex'), str(FIXTURES / 'stderr.hex'), str(code)],
        interpreter=interpreter, accept=accept, env={'LAUNCH_TOKEN': '${token}'})


def save_run(s, rows):
    write_json(s.run, dict(requirements=rows))


def requirement(identifier, *commands):
    return dict(id=identifier, commands=list(commands))


@pytest.fixture
def scenario(tmp_path):
    root = tmp_path / 'serviced application with spaces'
    root.mkdir()
    config = tmp_path / 'descriptions'
    config.mkdir()
    plugins = tmp_path / 'external plugins'
    plugins.mkdir()
    shutil.copyfile(FIXTURES / 'plugins.py', plugins / 'env2_launch_plugins.py')
    main = config / 'main.json'
    shutil.copyfile(FIXTURES / 'main.json', main)
    parameters = dict(python=sys.executable, directory=str(root), token='chosen launch token')
    values = config / 'values.json'
    write_json(values, parameters)
    objects = runpy.run_path(str(FIXTURES / 'plugins.py'))
    s = SimpleNamespace(root=root, main=main, run=config / 'run.json', parameters=parameters,
        values=values, plugins=plugins, foreign=tmp_path, trace=root / 'trace.jsonl',
        registry={name: objects[name + '_result'] for name in ('exit', 'opaque', 'broken')})
    s.registry['result'] = s.registry.pop('exit')
    s.lab = ConsoleLab(root)
    save_run(s, [requirement('one', probe(s, 'one')), requirement('two', probe(s, 'two'))])
    try:
        yield s
    finally:
        s.lab.close()


@pytest.fixture
def consoles(scenario):
    prepared = Path(os.environ['ENV2_XEPHYR_ROOT']).resolve()
    assert (prepared / 'usr/bin/Xephyr').is_file(), 'Prepare the visible X11 test server first'
    with visible_server(scenario.root, prepared / 'usr/bin/Xephyr',
                        prepared / 'usr/lib/x86_64-linux-gnu') as capture:
        try:
            yield capture
        finally:
            scenario.lab.close()


def invoke(s, selection='all', **changes):
    arguments = dict(config_path=s.main, operation='run', selection=selection,
        parameters=s.parameters, base_dir=s.root, interpreters=s.registry)
    arguments.update(changes)
    return public_api.prepare_resources(**arguments)


def cli(s, selection='all', *, omit=None, extra=(), config=None):
    pairs = [('--config', str(s.main if config is None else config)),
        ('--parameters', str(s.values)), ('--base-dir', str(s.root)),
        ('--requirements', selection if selection == 'all' else json.dumps(selection))]
    argv = [sys.executable, '-B', '-m', 'environment_maintenance', 'run']
    for flag, value in pairs:
        if flag != omit:
            argv += [flag, value]
    result = subprocess.run([*argv, *extra], cwd=s.foreign, capture_output=True, timeout=15,
        env=dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / 'src'), str(s.plugins)))))
    retain(s, 'cli', [*argv, *extra], result)
    return result


def retain(s, label, argv, result):
    number = len(list(s.root.glob('evidence-*.json')))
    prefix = 'evidence-' + str(number) + '-' + label
    write_json(s.root / (prefix + '.json'), dict(argv=argv, exit_code=result.returncode))
    (s.root / (prefix + '.stdout.bin')).write_bytes(result.stdout)
    (s.root / (prefix + '.stderr.bin')).write_bytes(result.stderr)


def trace(s):
    return [json.loads(line) for line in s.trace.read_text().splitlines()] if s.trace.exists() else []


def raw(record, field, encoded):
    value = record[field]
    if encoded:
        assert set(value) == {'encoding', 'data'} and value['encoding'] == 'base64'
        value = base64.b64decode(value['data'], validate=True)
    assert type(value) is bytes
    return value


def aggregate(result, ids, *, status='succeeded'):
    shapes = json.loads((FIXTURES / 'shapes.json').read_text())
    assert set(result) == set(shapes['aggregate'])
    assert result['operation'] == 'run' and result['status'] == status
    assert [row['id'] for row in result['requirements']] == ids
    if status == 'succeeded':
        assert result['error'] is None
    for index, row in enumerate(result['requirements']):
        assert set(row) == set(shapes['requirement'])
        assert set(row['result']) == set(shapes['action'])
        failed = status == 'failed' and index == len(ids) - 1
        assert row['result']['status'] == ('failed' if failed else 'succeeded')
        assert bool(row['result']['error']) if failed else row['result']['error'] is None
        for record in row['result']['commands']:
            assert set(record) == set(shapes['command'])


def cli_json(result, code=0):
    assert result.returncode == code, result.stderr.decode(errors='replace')
    assert result.stderr == b''
    assert result.stdout.endswith(b'\n') and len(result.stdout.splitlines()) == 1
    return json.loads(result.stdout)


def no_effects(s):
    assert trace(s) == []
    assert not list(s.root.glob('*.ready.json'))
    assert not list(s.root.glob('*.stdout'))
    assert not list(s.root.glob('*.stderr'))


def usage_cause(result):
    assert result.returncode == 2 and result.stdout == b''
    assert b'error:' in result.stderr
    return result.stderr.rsplit(b'error:', 1)[1]


def assert_missing_selected_plugin(result):
    assert result.returncode == 2 and result.stdout == b''
    assert result.stderr.startswith(b'interpreter result missing_selected_launch_plugin:exit_result: ')
    assert b"No module named 'missing_selected_launch_plugin'" in result.stderr


def tool(s, argv, *, log_names=('tool.stdout', 'tool.stderr'), extra=()):
    assert TOOL.is_file(), 'Missing required external console launch tool'
    args = ['--stdout-log', log_names[0], '--stderr-log', log_names[1], *extra, '--', *argv]
    argv = [sys.executable, '-B', str(TOOL), *args]
    result = subprocess.run(argv, cwd=s.root,
        env=dict(os.environ, LAUNCH_TOKEN='selected direct value'), capture_output=True, timeout=12)
    retain(s, 'tool', argv, result)
    return result


def submitted(result):
    value = cli_json(result)
    assert set(value) == {'status', 'pid'} and value['status'] == 'submitted'
    assert type(value['pid']) is int and value['pid'] > 0
    return value['pid']


def probe_argv(s, label, code=0):
    return [sys.executable, '-B', str(FIXTURES / 'probe.py'), str(s.root), label,
        str(FIXTURES / 'stdout.hex'), str(FIXTURES / 'stderr.hex'), str(code)]


def launch(s, label):
    argv = [sys.executable, '-B', str(TOOL), '--stdout-log', str(s.root / (label + '.stdout')),
            '--stderr-log', str(s.root / (label + '.stderr')), '--']
    argv += terminal_argv(sys.executable, FIXTURES / 'worker.py', s.root, label)
    return command(argv, env=dict(DISPLAY=os.environ['DISPLAY'], LAUNCH_TOKEN='${token}'))


def assert_binary_record(record, *, encoded=False, code=0, error=None):
    assert raw(record, 'stdout', encoded) == payload('stdout')
    assert raw(record, 'stderr', encoded) == payload('stderr')
    assert type(record['exit_code']) is int and record['exit_code'] == code
    assert record['error'] == error


def assert_rejected_second_command(result, record, *, encoded=False):
    assert_binary_record(record, encoded=encoded, code=9,
                         error='interpreter result: selected exit rejected')
    assert record['interpretation'] == dict(success=False, value=9, error='selected exit rejected')
    assert result['error'] == 'run requirement two: interpreter result: selected exit rejected'


def assert_logs(s, prefixes, repetitions=1):
    assert (s.root / 'tool.stdout').read_bytes() == prefixes[0] + payload('stdout') * repetitions
    assert (s.root / 'tool.stderr').read_bytes() == prefixes[1] + payload('stderr') * repetitions


def test_run_api_full_context_bytes_and_opaque(scenario):
    s = scenario
    save_run(s, [requirement('one', probe(s, 'one', interpreter='opaque'))])
    before = deepcopy(s.parameters)
    result = invoke(s)
    aggregate(result, ['one'])
    record = result['requirements'][0]['result']['commands'][0]
    assert_binary_record(record)
    assert record['interpretation']['value'] == payload('stdout')
    assert record['invocation'] == dict(argv=probe_argv(s, 'one'), cwd=str(s.root),
                                      env=dict(LAUNCH_TOKEN='chosen launch token'))
    assert s.parameters == before
    assert trace(s)[0]['token'] == 'chosen launch token'


def test_explicit_legacy_catalogue_run_keeps_its_contract(scenario):
    from v2_helpers import catalog, stateful_requirement
    s = scenario
    item, state, log = stateful_requirement(s.root, 'missing')
    selected = catalog(s.root, [item])
    result = subprocess.run([sys.executable, '-B', '-m', 'environment_maintenance',
        'run', '--catalog-dir', str(selected)], cwd=s.foreign, capture_output=True,
        env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), timeout=10)
    value = cli_json(result)
    assert value['schema'] == 'environment-maintenance/result/v2'
    assert value['status'] == 'ready'
    assert state.read_text() == 'satisfied'
    assert log.read_text().splitlines() == ['check', 'install', 'check']


@pytest.mark.parametrize('selection,expected', [('all', ['one', 'two']),
    (['two'], ['two']), (['two', 'one'], ['two', 'one']), ([], [])])
def test_run_selection_and_chain_order(scenario, selection, expected):
    s = scenario
    result = cli_json(cli(s, selection))
    aggregate(result, expected)
    assert [row['label'] for row in trace(s)] == expected
    for row in result['requirements']:
        assert_binary_record(row['result']['commands'][0], encoded=True)
    if not expected:
        no_effects(s)


@pytest.mark.parametrize('flag', ['--config', '--parameters', '--base-dir', '--requirements'])
def test_run_requires_each_explicit_working_argument(scenario, flag):
    result = cli(scenario, omit=flag)
    assert flag.encode() in usage_cause(result)
    no_effects(scenario)


def test_run_source_conflict_precedes_input_reading(scenario):
    missing = scenario.root / 'unreadable-config'
    result = cli(scenario, config=missing, extra=['--catalog-dir', str(missing)])
    cause = usage_cause(result)
    assert b'--config' in cause and b'--catalog-dir' in cause
    assert b'No such file' not in result.stderr
    no_effects(scenario)


@pytest.mark.parametrize('extra,flag', [(['--values', 'unused'], '--values'),
    (['--set', 'key=value'], '--set'), (['--dry-run'], '--dry-run')])
def test_run_source_rejects_catalogue_only_flags(scenario, extra, flag):
    result = cli(scenario, extra=extra)
    assert flag.encode() in usage_cause(result)
    no_effects(scenario)


@pytest.mark.parametrize('defect', ['template', 'interpreter', 'command'])
def test_run_preflights_late_commands_before_any_effect(scenario, defect):
    s = scenario
    late = probe(s, 'two')
    if defect == 'template':
        late['argv'][-1] = '${missing_launch_parameter}'
    elif defect == 'interpreter':
        late['interpreter']['name'] = 'missing_launch_interpreter'
    else:
        late['argv'] = []
    save_run(s, [requirement('one', probe(s, 'one')), requirement('two', late)])
    with pytest.raises(ValueError) as caught:
        invoke(s)
    assert 'run' in str(caught.value) and 'two' in str(caught.value)
    no_effects(s)


@pytest.mark.parametrize('defect', ['base', 'parameters', 'plugin'])
def test_run_empty_selection_still_validates_common_inputs(scenario, defect):
    s = scenario
    arguments = {}
    if defect == 'base':
        arguments['base_dir'] = 'relative-base'
    elif defect == 'parameters':
        arguments['parameters'] = []
    else:
        doc = json.loads(s.main.read_text())
        doc['interpreters']['result']['module'] = 'missing_selected_launch_plugin'
        write_json(s.main, doc)
        result = cli(s, [])
        assert_missing_selected_plugin(result)
        no_effects(s)
        return
    with pytest.raises(ValueError) as caught:
        invoke(s, [], **arguments)
    assert str(caught.value)
    no_effects(s)


@pytest.mark.parametrize('encoded', [False, True])
def test_run_full_binary_and_selected_nonzero_interpreter(scenario, encoded):
    s = scenario
    save_run(s, [requirement('one', probe(s, 'one', code=7, accept=(7,)))])
    result = cli_json(cli(s)) if encoded else invoke(s)
    aggregate(result, ['one'])
    record = result['requirements'][0]['result']['commands'][0]
    assert_binary_record(record, encoded=encoded, code=7)
    assert record['interpretation'] == dict(success=True, value=7, error=None)


def test_run_plugin_failure_preserves_attempted_raw_data_and_stops_tail(scenario):
    s = scenario
    save_run(s, [requirement('one', probe(s, 'one', interpreter='broken'), probe(s, 'tail'))])
    result = invoke(s)
    aggregate(result, ['one'], status='failed')
    record = result['requirements'][0]['result']['commands'][0]
    assert raw(record, 'stdout', False) == payload('stdout')
    assert raw(record, 'stderr', False) == payload('stderr')
    assert 'selected interpreter refused launch result' in str(record['error'])
    assert [row['label'] for row in trace(s)] == ['one']


@pytest.mark.parametrize('existing', [False, True])
def test_console_tool_preserves_complete_distinct_logs_and_real_command_context(scenario, existing):
    s = scenario
    prefixes = (b'prior-out\x00\xff', b'prior-err\xfe\x00') if existing else (b'', b'')
    for filename, prefix in zip(('tool.stdout', 'tool.stderr'), prefixes, strict=True):
        if existing:
            (s.root / filename).write_bytes(prefix)
    pid = submitted(tool(s, probe_argv(s, 'direct')))
    wait_for(lambda: (s.root / 'direct.done').is_file(), 'probe completed and both streams flushed')
    row = trace(s)[0]
    assert row['pid'] == pid and row['cwd'] == str(s.root)
    assert row['argv'] == probe_argv(s, 'direct')[3:]
    assert row['token'] == 'selected direct value'
    assert_logs(s, prefixes)
    if existing:
        second_pid = submitted(tool(s, probe_argv(s, 'again')))
        wait_for(lambda: (s.root / 'again.done').is_file(), 'second probe completed and flushed')
        assert trace(s)[1]['pid'] == second_pid
        assert_logs(s, prefixes, 2)


@pytest.mark.parametrize('existing', [False, True])
def test_console_tool_same_literal_log_path_is_rejected_before_open_or_spawn(scenario, existing):
    s = scenario
    path = s.root / 'same.log'
    before = b'known-original\x00\xff'
    if existing:
        path.write_bytes(before)
    result = tool(s, probe_argv(s, 'forbidden'), log_names=('same.log', 'same.log'))
    cause = usage_cause(result)
    assert b'stdout' in cause and b'stderr' in cause and b'same.log' in cause
    assert path.read_bytes() == before if existing else not path.exists()
    assert trace(s) == [] and not (s.root / 'forbidden.done').exists()


@pytest.mark.parametrize('failure', ['executable', 'stdout', 'stderr'])
def test_console_tool_failure_retains_existing_bytes_and_truthful_partial_setup(scenario, failure):
    s = scenario
    names = ['tool.stdout', 'tool.stderr']
    old = b'prior-complete\x00\xff'
    (s.root / 'tool.stdout').write_bytes(old)
    (s.root / 'tool.stderr').write_bytes(old)
    argv = probe_argv(s, 'forbidden')
    if failure == 'executable':
        argv[0] = str(s.root / 'missing-executable')
        expected = b'missing-executable'
    else:
        names[0 if failure == 'stdout' else 1] = 'missing-parent/log'
        expected = b'missing-parent'
    result = tool(s, argv, log_names=names)
    assert result.returncode == 1 and result.stdout == b'' and expected in result.stderr
    for name in ('tool.stdout', 'tool.stderr'):
        assert (s.root / name).read_bytes() == old
    assert trace(s) == [] and not (s.root / 'forbidden.done').exists()


@pytest.mark.parametrize('bad_index', [0, 1])
def test_console_tool_open_failure_allows_only_empty_new_other_log(scenario, bad_index):
    s = scenario
    names = ['new.stdout', 'new.stderr']
    names[bad_index] = 'absent-parent/log'
    result = tool(s, probe_argv(s, 'forbidden'), log_names=names)
    assert result.returncode == 1 and result.stdout == b'' and b'absent-parent' in result.stderr
    other = s.root / names[1 - bad_index]
    assert not other.exists() or other.read_bytes() == b''
    assert trace(s) == []


@pytest.mark.parametrize('arguments,reason', [([], b'--stdout-log'),
    (['--stdout-log', 'out'], b'--stderr-log'),
    (['--stderr-log', 'err'], b'--stdout-log'),
    (['--stdout-log', 'out', '--stderr-log', 'err', '--'], b'command')])
def test_console_tool_requires_explicit_log_paths_and_command(scenario, arguments, reason):
    assert TOOL.is_file(), 'Missing required external console launch tool'
    result = subprocess.run([sys.executable, '-B', str(TOOL), *arguments],
        cwd=scenario.root, capture_output=True, timeout=5)
    retain(scenario, 'tool-arguments', [sys.executable, '-B', str(TOOL), *arguments], result)
    assert reason in usage_cause(result).lower()
    assert all(path.name.startswith('evidence-') for path in scenario.root.iterdir())


def test_run_two_visible_consoles_return_eof_and_stop_independently(scenario, consoles):
    s = scenario
    save_run(s, [requirement('one', launch(s, 'one'), probe(s, 'after-one')),
                 requirement('two', launch(s, 'two'), probe(s, 'after-two'))])
    completed = cli(s)
    result = cli_json(completed)
    aggregate(result, ['one', 'two'])
    rows = [s.lab.ready(label) for label in ('one', 'two')]
    assert rows[0]['window'] != rows[1]['window'] and rows[0]['tty'] != rows[1]['tty']
    for label, row, requirement_row in zip(('one', 'two'), rows, result['requirements'], strict=True):
        s.lab.screenshot(label)
        records = requirement_row['result']['commands']
        assert len(records) == 2
        answer = json.loads(raw(records[0], 'stdout', True))
        assert set(answer) == {'status', 'pid'} and answer['status'] == 'submitted'
        assert type(answer['pid']) is int and answer['pid'] == row['parent']
        assert raw(records[0], 'stderr', True) == b''
        assert records[0]['exit_code'] == 0 and records[0]['error'] is None
        assert_binary_record(records[1], encoded=True)
        assert row['cwd'] == str(s.root) and row['token'] == 'chosen launch token'
        s.lab.reply(label, '314')
    consoles()
    assert [row['label'] for row in trace(s)] == ['after-one', 'after-two']
    s.lab.stop('one')
    assert not (s.root / 'two.stopped.json').exists()
    s.lab.reply('two', '271')
    s.lab.stop('two')


def test_console_tool_returns_with_live_visible_worker_and_exact_terminal_pid(scenario, consoles):
    s = scenario
    pid = submitted(tool(s, terminal_argv(sys.executable, FIXTURES / 'worker.py', s.root, 'direct')))
    row = s.lab.ready('direct')
    assert row['parent'] == pid and row['token'] == 'selected direct value'
    s.lab.screenshot('direct')
    s.lab.reply('direct', '314')
    consoles()
    s.lab.stop('direct')


def test_run_late_failure_keeps_first_console_and_never_launches_tail(scenario, consoles):
    s = scenario
    save_run(s, [requirement('one', launch(s, 'one')),
        requirement('two', probe(s, 'failure', code=9), launch(s, 'forbidden')),
        requirement('three', probe(s, 'tail'))])
    result = cli_json(cli(s), 1)
    aggregate(result, ['one', 'two'], status='failed')
    record = result['requirements'][1]['result']['commands'][0]
    assert_rejected_second_command(result, record, encoded=True)
    assert len(result['requirements'][1]['result']['commands']) == 1
    assert [row['label'] for row in trace(s)] == ['failure']
    assert not (s.root / 'forbidden.ready.json').exists()
    s.lab.ready('one')
    s.lab.screenshot('one')
    s.lab.reply('one', '271')
    consoles()
    s.lab.stop('one')
