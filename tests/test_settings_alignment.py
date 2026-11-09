"""Configured adjustment and real external-tool effects with independent oracles."""
import base64
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from environment_maintenance import prepare_resources


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/settings-alignment'
TOOL = ROOT / 'examples/settings-alignment/align_queue.py'


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


@pytest.fixture
def scenario(tmp_path):
    root = tmp_path / 'serviced application with spaces'
    root.mkdir()
    actions = tmp_path / 'action descriptions'
    actions.mkdir()
    settings = tmp_path / 'mutable settings'
    settings.mkdir()
    plugins = tmp_path / 'external plugins'
    plugins.mkdir()
    for name in ('actions-main.json', 'adjust.json', 'foreign.json'):
        shutil.copyfile(FIXTURES / name, actions / name)
    shutil.copyfile(FIXTURES / 'settings-main.json', settings / 'main.json')
    target = settings / 'applications.json'
    shutil.copyfile(FIXTURES / 'applications-before.json', target)
    shutil.copyfile(FIXTURES / 'plugins.py', plugins / 'env2_alignment_plugins.py')
    parameters = fixture('parameters.json')
    parameters.update(python=sys.executable, probe=str(FIXTURES / 'probe.py'),
        target_document=str(target), trace=str(root / 'trace.jsonl'), tool=str(TOOL),
        settings_config=str(settings / 'main.json'), source_path=str(ROOT / 'src'))
    values = actions / 'values.json'
    write_json(values, parameters)
    immutable = [actions / name for name in ('actions-main.json', 'adjust.json', 'foreign.json')]
    immutable += [settings / 'main.json', values]
    return SimpleNamespace(root=root, foreign_cwd=tmp_path, main=actions / 'actions-main.json',
        adjust=actions / 'adjust.json', settings=settings / 'main.json', target=target,
        values=values, parameters=parameters, trace=root / 'trace.jsonl', plugins=plugins,
        registry={'chosen': runpy.run_path(str(FIXTURES / 'plugins.py'))['exit_result']},
        original={path: path.read_bytes() for path in immutable}, before=target.read_bytes())


def update_values(s, **changes):
    s.parameters.update(changes)
    write_json(s.values, s.parameters)
    s.original[s.values] = s.values.read_bytes()


def run_cli(s, selection='all', *, base_dir=None, extra=()):
    argv = [sys.executable, '-B', '-m', 'environment_maintenance', 'adjust',
        '--config', str(s.main), '--parameters', str(s.values),
        '--base-dir', str(s.root if base_dir is None else base_dir),
        '--requirements', selection, *extra]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / 'src'), str(s.plugins))))
    return subprocess.run(argv, cwd=s.foreign_cwd, env=env, capture_output=True)


def require_tool():
    # This capability assertion is in test bodies, never a fixture/setup error.
    assert TOOL.is_file(), 'Missing required queue alignment example'


def run_tool(s, *, reader='reader', variable='QUEUE_NAME', queue='billing.jobs'):
    require_tool()
    return subprocess.run([sys.executable, '-B', str(TOOL),
        '--config', str(s.settings), '--operation', 'applications',
        '--writer', 'writer', '--reader', reader,
        '--queue-variable', variable, '--queue', queue],
        cwd=s.foreign_cwd, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
        capture_output=True)


def preserved(s):
    for path, raw in s.original.items():
        assert path.read_bytes() == raw


def no_effects(s):
    assert s.target.read_bytes() == s.before
    assert not s.trace.exists()
    preserved(s)


def target_matches(s, name='applications-after.json'):
    actual = json.loads(s.target.read_text(encoding='utf-8'))
    assert canonical(actual) == canonical(fixture(name))


def trace_matches(s, name):
    actual = [json.loads(line) for line in s.trace.read_text().splitlines()]
    assert canonical(actual) == canonical(fixture(name))


def decoded(record, field, encoded):
    value = record[field]
    if encoded:
        assert set(value) == {'encoding', 'data'} and value['encoding'] == 'base64'
        value = base64.b64decode(value['data'], validate=True)
    assert type(value) is bytes
    return value


def probe_result(record, phase, encoded):
    expected = {
        'note': (b'\xffnote\x00\n', b'probe:note\n'),
        'observed': (b'\xffobserved\x00\n', b'probe:observed\n'),
        'tail': (b'\xfftail\x00\n', b'probe:tail\n'),
    }
    assert decoded(record, 'stdout', encoded) == expected[phase][0]
    assert decoded(record, 'stderr', encoded) == expected[phase][1]


def success(s, result, identifiers, trace_fixture, *, encoded,
            target_fixture='applications-after.json', tool_fixture='tool-success.json'):
    assert set(result) == {'operation', 'status', 'requirements', 'error'}
    assert result['operation'] == 'adjust' and result['status'] == 'succeeded'
    assert result['error'] is None
    assert [row['id'] for row in result['requirements']] == identifiers
    for row in result['requirements']:
        action = row['result']
        assert action['status'] == 'succeeded' and action['error'] is None
        expected_count = 2 if row['id'] == 'queue-agreement' else 1
        assert len(action['commands']) == expected_count
        for command in action['commands']:
            assert type(command['exit_code']) is int and command['exit_code'] == 0
            assert command['error'] is None
            assert command['invocation']['cwd'] == str(s.root)
            assert command['interpreter']['name'] == 'chosen'
            assert command['interpretation'] == dict(success=True, value=0, error=None)
        if row['id'] == 'queue-agreement':
            tool, observer = action['commands']
            assert tool['invocation']['env'] == dict(PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1')
            raw = decoded(tool, 'stdout', encoded)
            assert raw.endswith(b'\n') and len(raw.splitlines()) == 1
            assert canonical(json.loads(raw)) == canonical(fixture(tool_fixture))
            assert decoded(tool, 'stderr', encoded) == b''
            assert observer['invocation']['env'] == {}
            probe_result(observer, 'observed', encoded)
        else:
            assert action['commands'][0]['invocation']['env'] == {}
            probe_result(action['commands'][0], row['id'], encoded)
    target_matches(s, target_fixture)
    trace_matches(s, trace_fixture)
    preserved(s)


def cli_json(process, *, exit_code=0):
    assert process.returncode == exit_code, 'Missing required adjust CLI behavior'
    assert process.stderr == b''
    assert process.stdout.endswith(b'\n') and len(process.stdout.splitlines()) == 1
    return json.loads(process.stdout)


def test_cli_adjust_selects_own_description_and_real_alignment(scenario):
    result = cli_json(run_cli(scenario))
    success(scenario, result, ['note', 'queue-agreement', 'tail'], 'trace-all.json', encoded=True)


def test_cli_adjust_runs_only_selected_requirement(scenario):
    update_values(scenario, reader='cache', queue='reports.jobs')
    result = cli_json(run_cli(scenario, '["queue-agreement"]'))
    success(scenario, result, ['queue-agreement'], 'trace-selected.json', encoded=True,
            target_fixture='applications-after-reports.json', tool_fixture='tool-success-reports.json')


def test_cli_adjust_empty_selection_has_no_effects(scenario):
    result = cli_json(run_cli(scenario, '[]'))
    assert result == dict(operation='adjust', status='succeeded', requirements=[], error=None)
    no_effects(scenario)


def test_public_api_adjust_preserves_bytes_and_real_settings(scenario):
    require_tool()
    result = prepare_resources(scenario.main, 'adjust', 'all', scenario.parameters,
                               base_dir=scenario.root, interpreters=scenario.registry)
    success(scenario, result, ['note', 'queue-agreement', 'tail'], 'trace-all.json', encoded=False)


def test_external_tool_aligns_selected_settings_and_preserves_other_data(scenario):
    process = run_tool(scenario, variable='OTHER_QUEUE', queue='archive.jobs')
    assert process.returncode == 0 and process.stderr == b''
    assert process.stdout.endswith(b'\n') and len(process.stdout.splitlines()) == 1
    assert canonical(json.loads(process.stdout)) == canonical(fixture('tool-success-other.json'))
    target_matches(scenario, 'applications-after-other.json')
    assert not scenario.trace.exists()
    preserved(scenario)


def test_adjust_failure_preserves_prior_work_and_complete_cause(scenario):
    update_values(scenario, reader='unknown-reader')
    result = cli_json(run_cli(scenario), exit_code=1)
    assert result['operation'] == 'adjust' and result['status'] == 'failed'
    assert 'adjust' in result['error'] and 'queue-agreement' in result['error']
    assert [row['id'] for row in result['requirements']] == ['note', 'queue-agreement']
    note, failed = [row['result'] for row in result['requirements']]
    assert note['status'] == 'succeeded' and len(note['commands']) == 1
    probe_result(note['commands'][0], 'note', True)
    assert failed['status'] == 'failed' and len(failed['commands']) == 1
    command = failed['commands'][0]
    assert type(command['exit_code']) is int and command['exit_code'] == 1
    assert command['interpretation'] == dict(success=False, value=1, error='external process failed')
    assert decoded(command, 'stdout', True) == b''
    diagnostic = decoded(command, 'stderr', True)
    assert b'unknown-reader' in diagnostic and diagnostic
    assert command['error']
    assert scenario.target.read_bytes() == scenario.before
    trace_matches(scenario, 'trace-partial.json')
    preserved(scenario)


def test_external_tool_validates_both_selected_ids_before_writing(scenario):
    process = run_tool(scenario, reader='unknown-reader')
    assert process.returncode == 1 and process.stdout == b''
    assert b'unknown-reader' in process.stderr
    no_effects(scenario)


@pytest.mark.parametrize('invalid', ['relative-base', 'nonscalar'])
def test_adjust_empty_selection_validates_common_inputs(scenario, invalid):
    kwargs = {}
    if invalid == 'relative-base':
        kwargs['base_dir'] = 'relative'
    else:
        update_values(scenario, queue=[])
    process = run_cli(scenario, '[]', **kwargs)
    assert process.returncode == 2 and process.stdout == b''
    cause = process.stderr.decode().splitlines()[-1].lower()
    assert ('base' in cause if invalid == 'relative-base' else 'scalar' in cause), process.stderr.decode()
    no_effects(scenario)


@pytest.mark.parametrize('number', ['1e400', '1e300'])
def test_adjust_preflights_selected_json_metadata_and_accepts_finite_control(scenario, number):
    original = scenario.adjust.read_text()
    token = '"transport_number": 0'
    assert original.count(token) == 1
    scenario.adjust.write_text(original.replace(token, '"transport_number": ' + number), encoding='utf-8')
    scenario.original[scenario.adjust] = scenario.adjust.read_bytes()
    process = run_cli(scenario)
    if number == '1e400':
        assert process.returncode == 2 and process.stdout == b''
        assert 'json' in process.stderr.decode().splitlines()[-1].lower(), process.stderr.decode()
        no_effects(scenario)
    else:
        result = cli_json(process)
        success(scenario, result, ['note', 'queue-agreement', 'tail'], 'trace-all.json', encoded=True)
        options = result['requirements'][1]['result']['commands'][0]['interpreter']['options']
        assert options['transport_number'] == 1e300


@pytest.mark.parametrize('arguments', [
    ('--catalog-dir', 'unused-catalog'),
    ('--values', 'unused-values.json'),
    ('--set', 'queue=ignored'),
    ('--dry-run',),
])
def test_adjust_warns_about_foreign_flag_and_runs_effects(scenario, arguments):
    process = run_cli(scenario, extra=arguments)
    assert process.returncode == 0, process.stderr
    assert arguments[0].encode() in process.stderr
    success(scenario, json.loads(process.stdout), ['note', 'queue-agreement', 'tail'],
            'trace-all.json', encoded=True)
