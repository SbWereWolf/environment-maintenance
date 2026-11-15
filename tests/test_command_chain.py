"""Independent contract for the new public chain, not a runtime implementation."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from threading import Event

import pytest
import command_execution as package
from command_execution import execute_action

FIXTURES = Path(__file__).parent / 'fixtures' / 'command-chain'
CASES = json.loads((FIXTURES / 'cases.json').read_text())


def typed_equal(actual, expected):
    assert type(actual) is type(expected)
    assert json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)


def command(token, **changes):
    row = json.loads((FIXTURES / 'command.json').read_text())
    row['argv'] = ['worker', token]
    row.update(changes)
    return row


def public(name):
    operation = getattr(package, name, None)
    assert callable(operation), f'NEW-CHAIN-CONTRACT: missing public {name}'
    return operation


class Answers:
    """Consumer-provided interpreter; explicit fixtures own every answer."""
    def __init__(self, answers=None):
        self.answers = answers or {}
        self.calls = []

    def interpret(self, raw, options):
        token = raw['stdout'].decode()
        self.calls.append(token)
        answer = self.answers.get(token, {'success': True, 'value': 'opaque', 'error': None})
        if isinstance(answer, Exception):
            raise answer
        return deepcopy(answer)


class Runner:
    def __init__(self):
        self.seen = []
        self.codes = {}
        self.failures = {}

    def __call__(self, invocation):
        self.seen.append(deepcopy(invocation))
        token = invocation['argv'][1]
        if token in self.failures:
            raise self.failures[token]
        return dict(exit_code=self.codes.get(token, 0), stdout=token.encode(), stderr=b'')


def execute(tmp_path, rows, *, data=None, interpreter=None, runner=None, **options):
    return public('execute_chain')(
        {'commands': rows}, CASES['original_parameters'],
        input_data=deepcopy(CASES['initial'] if data is None else data),
        base_dir=tmp_path, interpreters={'result': interpreter or Answers()},
        run_command=runner or Runner(), **options,
    )


def inputs(runner):
    return [json.loads(item['stdin']) for item in runner.seen]


def test_existing_control_uses_real_process(tmp_path):
    """A missing new API is RED only after this real old invocation passes."""
    from command_execution.actions.process import run_command
    import environment_maintenance
    assert Path(environment_maintenance.__file__).resolve().parents[2] == Path(__file__).parents[1]
    assert '/.venv/' in str(Path(package.__file__).resolve())
    row = command('control')
    row['argv'] = [sys.executable, '-c', 'import sys;sys.stdout.buffer.write(b"control");sys.exit(7)']
    row.pop('enabled'); row.pop('on_error')
    class AcceptSeven:
        def interpret(self, raw, options):
            return {'success': raw['exit_code'] == 7, 'value': 'accepted-seven', 'error': None}
    result = execute_action({'commands': [row]}, {}, base_dir=tmp_path,
                            interpreters={'result': AcceptSeven()})
    assert result['status'] == 'succeeded'
    assert result['commands'][0]['stdout'] == b'control'
    assert result['commands'][0]['exit_code'] == 7
    assert callable(run_command)


def test_sync_data_order_defaults_and_fixed_substitutions(tmp_path):
    runner = Runner()
    answers = Answers({'first': {'success': True, 'value': CASES['opaque_value'],
                                 'error': None, 'next_input': CASES['changed']}})
    rows = [command('first'), command('${token}')]
    original = deepcopy(rows)
    result = execute(tmp_path, rows, interpreter=answers, runner=runner)
    assert [r['argv'][1] for r in runner.seen] == ['first', 'original']
    assert inputs(runner) == [CASES['initial'], CASES['changed']]
    assert result['data'] == CASES['changed']
    assert rows == original
    assert CASES['initial'] == {'step': 'original', 'nested': [1]}


@pytest.mark.parametrize('value', CASES['falsey'])
def test_explicit_falsey_and_null_are_transferred(tmp_path, value):
    runner = Runner()
    answers = Answers({'first': {'success': True, 'value': 'different',
                                 'error': None, 'next_input': value}})
    result = execute(tmp_path, [command('first'), command('last')],
                     interpreter=answers, runner=runner)
    typed_equal(inputs(runner)[1], value)
    typed_equal(result['data'], value)


def test_interpretation_value_alone_does_not_change_data(tmp_path):
    runner = Runner()
    answers = Answers({'first': {'success': True, 'value': CASES['opaque_value'], 'error': None}})
    result = execute(tmp_path, [command('first'), command('last')],
                     interpreter=answers, runner=runner)
    assert inputs(runner) == [CASES['initial'], CASES['initial']]
    assert result['data'] == CASES['initial']


@pytest.mark.parametrize('failure', ['rejected', 'launch', 'interpreter', 'malformed'])
@pytest.mark.parametrize('policy', ['continue', 'stop'])
def test_sync_failure_policy_preserves_last_valid_input(tmp_path, failure, policy):
    runner = Runner()
    answers = Answers()
    if failure == 'launch':
        runner.failures['first'] = OSError('launch refused')
    elif failure == 'interpreter':
        answers.answers['first'] = ValueError('interpret refused')
    elif failure == 'malformed':
        answers.answers['first'] = {'success': 'wrong'}
    else:
        answers.answers['first'] = {'success': False, 'value': None, 'error': 'rejected'}
    result = execute(tmp_path, [command('first', on_error=policy), command('last')],
                     interpreter=answers, runner=runner)
    assert [r['argv'][1] for r in runner.seen] == (
        ['first', 'last'] if policy == 'continue' else ['first'])
    assert all(v == CASES['initial'] for v in inputs(runner))
    assert result['data'] == CASES['initial']
    assert result['commands'][0]['error']
    if failure in ('launch', 'interpreter'):
        exc = result['commands'][0]['exception']
        assert exc['type'] == ('OSError' if failure == 'launch' else 'ValueError')
        assert 'refused' in exc['message']
    if failure == 'launch':
        assert result['commands'][0]['exit_code'] is None


def test_success_is_interpreted_not_exit_code(tmp_path):
    runner = Runner()
    runner.codes['first'] = 7
    result = execute(tmp_path, [command('first'), command('last')], runner=runner)
    assert len(runner.seen) == 2
    assert result['status'] == 'succeeded'
    assert result['commands'][0]['exit_code'] == 7


@pytest.mark.parametrize('failure', [None, 'rejected', 'launch', 'interpreter', 'malformed'])
def test_async_snapshot_never_aborts_and_delivers_late_result(tmp_path, failure):
    # Causal proof: the sync child releases a blocked background runner.
    gate, began, delivered = Event(), Event(), Event()
    runner = Runner()
    answers = Answers({'change': {'success': True, 'value': 'opaque', 'error': None,
                                  'next_input': CASES['changed']}})
    if failure == 'rejected':
        answers.answers['background'] = {'success': False, 'value': None, 'error': 'rejected'}
    elif failure == 'interpreter':
        answers.answers['background'] = ValueError('late interpreter refusal')
    elif failure == 'malformed':
        answers.answers['background'] = {'success': 'wrong'}
    if failure == 'launch':
        runner.failures['background'] = OSError('late launch refusal')
    records = []
    after = []
    trace = []
    barrier_failures = []
    caller_input = deepcopy(CASES['initial'])
    def observe(record):
        if record['index'] == 0:
            records.append(deepcopy(record))
            delivered.set()
    def controlled(invocation):
        token = invocation['argv'][1]
        if token == 'background':
            trace.append('background-start')
            began.set()
            if not gate.wait(10):
                barrier_failures.append('next sync command did not release background')
                raise AssertionError('test barrier did not open')
            trace.append('background-finish')
        elif token == 'change':
            assert began.wait(10), 'test barrier: background was never dispatched'
            assert not delivered.is_set(), 'background completed before next command'
            caller_input['nested'].append(99)
        else:
            after.append(json.loads(invocation['stdin']))
            trace.append('last-command')
            gate.set()
        return runner(invocation)
    try:
        result = public('execute_chain')(
            {'commands': [command('background', mode='async', on_error='stop'),
                          command('change'), command('last')]}, {},
            input_data=caller_input, base_dir=tmp_path, interpreters={'result': answers},
            run_command=controlled, on_result=observe)
        assert after == [CASES['changed']]
        assert result['data'] == CASES['changed']
        assert delivered.wait(10), 'late result was not delivered to consumer'
        assert not barrier_failures, barrier_failures
        assert trace.index('last-command') < trace.index('background-finish')
        row = records[0]
        if failure is None:
            assert row['error'] is None
        assert row['input_data'] == CASES['initial']
        if failure:
            assert row['error']
        if failure in ('launch', 'interpreter'):
            assert 'late' in row['exception']['message']
        assert result['data'] == CASES['changed']
    finally:
        gate.set()


def test_disabled_record_is_retained_and_not_invoked(tmp_path):
    runner = Runner()
    answers = Answers()
    rows = [command('first'), command('disabled', enabled=False), command('last')]
    plan = public('plan_chain')({'commands': rows}, {}, input_data=CASES['initial'],
                                base_dir=tmp_path, interpreters={'result': answers})
    assert [r['enabled'] for r in plan['commands']] == [True, False, True]
    execute(tmp_path, rows, runner=runner, interpreter=answers)
    assert [r['argv'][1] for r in runner.seen] == ['first', 'last']
    assert answers.calls == ['first', 'last']
    assert len(rows) == 3
    assert inputs(runner) == [CASES['initial'], CASES['initial']]


def test_dry_run_prepares_exact_values_without_execution_or_interpretation(tmp_path, monkeypatch):
    class Forbidden:
        def interpret(self, raw, options):
            pytest.fail('dry-run invoked interpreter')
    def forbidden(*args, **kwargs):
        pytest.fail('dry-run attempted process or background dispatch')
    from threading import Thread
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(Thread, 'start', forbidden)
    rows = [command('${token}'), command('${token}', mode='async')]
    before = deepcopy(rows)
    plan = public('plan_chain')({'commands': rows}, {'token': 'supplied'},
                                input_data=CASES['initial'], base_dir=tmp_path,
                                interpreters={'result': Forbidden()})
    row = plan['commands'][0]
    assert row['argv'] == ['worker', 'supplied']
    assert row['cwd'] == str(tmp_path)
    assert row['env'] == {}
    assert row['mode'] == 'sync'
    assert rows == before
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(ValueError, match='token'):
        public('plan_chain')({'commands': rows}, {}, input_data=CASES['initial'],
                             base_dir=tmp_path, interpreters={'result': Forbidden()})


def test_real_process_transfers_input_and_preserves_full_streams(tmp_path):
    first, second = tmp_path / 'first.json', tmp_path / 'second.json'
    rows = [command('first'), command('last')]
    for row, target, action in zip(rows, [first, second], ['echo', 'bytes']):
        row['argv'] = [sys.executable, str(FIXTURES / 'child.py'), str(target), action, '7']
    class Wire:
        def interpret(self, raw, options):
            result = {'success': raw['exit_code'] == 7, 'value': None, 'error': None}
            if raw['stdout'].startswith(b'{'):
                result['next_input'] = json.loads(raw['stdout'])
            return result
    result = public('execute_chain')({'commands': rows}, {}, input_data=CASES['initial'],
                                     base_dir=tmp_path, interpreters={'result': Wire()})
    assert json.loads(first.read_bytes()) == CASES['initial']
    assert json.loads(second.read_bytes()) == {'step': 'child-changed', 'nested': [1]}
    assert result['data'] == {'step': 'child-changed', 'nested': [1]}
    last = result['commands'][-1]
    assert last['stdout'] == b'out\x00\xff' * 32768
    assert last['stderr'] == b'err\x00\xfe' * 32768
    assert last['exit_code'] == 7


def test_installed_wheel_uses_new_public_contract(tmp_path):
    import os
    import shutil
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'package-source'
    shutil.copytree(root / 'packages' / 'command-execution', source,
                    ignore=shutil.ignore_patterns('__pycache__', '*.egg-info', 'build', 'dist'))
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    def run(argv):
        return subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True)
    wheel_dir = tmp_path / 'wheels'
    built = run([sys.executable, '-I', '-B', '-m', 'build', '--wheel', '--no-isolation',
                 '--outdir', str(wheel_dir), str(source)])
    assert built.returncode == 0, (built.stdout, built.stderr)
    wheels = list(wheel_dir.glob('*.whl'))
    assert len(wheels) == 1
    target = tmp_path / 'installed'
    installed = run([sys.executable, '-I', '-B', '-m', 'pip', 'install', '--no-index',
                     '--no-deps', '--target', str(target), str(wheels[0])])
    assert installed.returncode == 0, (installed.stdout, installed.stderr)
    observed = run([sys.executable, '-I', '-B', str(FIXTURES / 'installed.py'),
                    str(target), str(FIXTURES.resolve()), str(tmp_path)])
    assert observed.returncode == 0, (observed.stdout, observed.stderr)
    assert observed.stdout == b'installed-chain-contract-ok\n'


def test_valid_sync_failure_output_is_forwarded_on_continue(tmp_path):
    runner = Runner()
    answers = Answers({'first': {'success': False, 'value': 'opaque',
                                 'error': 'rejected', 'next_input': CASES['changed']}})
    result = execute(tmp_path, [command('first', mode='sync', on_error='continue'),
                               command('last')], runner=runner, interpreter=answers)
    assert inputs(runner) == [CASES['initial'], CASES['changed']]
    assert result['data'] == CASES['changed']
    assert result['commands'][0]['error']


def test_caller_data_and_configuration_remain_owned_by_caller(tmp_path):
    original = deepcopy(CASES['initial'])
    rows = [command('first')]
    before = deepcopy(rows)
    answers = Answers({'first': {'success': True, 'value': None, 'error': None,
                                 'next_input': CASES['changed']}})
    public('execute_chain')({'commands': rows}, {}, input_data=original,
                            base_dir=tmp_path, interpreters={'result': answers},
                            run_command=Runner())
    assert original == CASES['initial']
    assert rows == before
