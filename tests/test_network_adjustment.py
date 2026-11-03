"""Shared adjust at its real CLI, kernel and single-file publication boundaries."""
import builtins
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from copy import deepcopy
import errno
import io
import json
import os
from pathlib import Path
import selectors
import re
import socket
import stat
import subprocess
import sys
from types import SimpleNamespace
from urllib.request import urlopen

import pytest

from environment_maintenance import prepare_resources
from environment_maintenance.cli import main


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tests/fixtures/network-adjustment'
SECRET = 'unrelated-private-sentinel-network-test'


def record(value):
    """The existing runner may retain full fixture observations as a declared output."""
    destination = os.environ.get('POISE_RUN_OUTPUT_DIR')
    if destination:
        with (Path(destination) / 'network-observations.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')


def record_cli(process, cwd):
    record(dict(kind='cli', argv=process.args, cwd=str(cwd), exit_code=process.returncode,
                stdout=process.stdout.decode('utf-8'), stderr=process.stderr.decode('utf-8')))
    return process


def fixture(name):
    return json.loads((DATA / name).read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def profile(s, value):
    write(s.adjust, value)
    s.inputs[s.adjust] = s.adjust.read_bytes()


@pytest.fixture
def scenario(tmp_path):
    home = tmp_path / 'instance with spaces'
    home.mkdir()
    settings = home / 'selected settings'
    settings.mkdir()
    s = SimpleNamespace(home=home, main=home / 'main.json', adjust=home / 'adjust.json',
        values=settings / 'subject parameters.json', default=home / 'default parameters.json',
        trace=home / 'must-not-run.txt', inputs={})
    write(s.main, fixture('main.json'))
    write(s.default, fixture('other-parameters.json'))
    write(s.values, fixture('parameters.json'))
    s.values.chmod(0o640)
    s.inputs = {path: path.read_bytes() for path in (s.main, s.default)}
    profile(s, fixture('adjust.json'))
    return s


def multi(s):
    profile(s, fixture('multi-adjust.json'))
    write(s.values, fixture('multi-parameters.json'))


def arguments(s, selection='all'):
    return ['adjust', '--config', str(s.main), '--parameters', str(s.values),
            '--base-dir', str(s.home), '--requirements', selection]


def invoke(s, selection='all'):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / 'src'),
        str(DATA))), PYTHONDONTWRITEBYTECODE='1')
    process = subprocess.run([sys.executable, '-B', '-m', 'environment_maintenance',
        *arguments(s, selection)], cwd=s.home, env=env, capture_output=True, timeout=15)
    return record_cli(process, s.home)


def invoke_here(s, selection='all'):
    """Only OS-fault tests need in-process access to the same public CLI main."""
    output, errors = io.StringIO(), io.StringIO()
    with redirect_stdout(output), redirect_stderr(errors):
        try:
            code = main(arguments(s, selection))
        except SystemExit as error:
            code = error.code
    process = subprocess.CompletedProcess(arguments(s, selection), code,
        output.getvalue().encode(), errors.getvalue().encode())
    return record_cli(process, Path.cwd())


def response(process, code=0):
    if process.returncode != code:
        message = ('NETWORK_ADJUST_REQUIRED: expected exit ' + str(code)
                   + ', got ' + str(process.returncode) + '; stderr='
                   + process.stderr.decode('utf-8').strip())
        print(message)
        pytest.fail(message, pytrace=False)
    assert process.stderr == b''
    assert process.stdout.endswith(b'\n') and len(process.stdout.splitlines()) == 1
    assert SECRET.encode() not in process.stdout + process.stderr
    assert b'other-instance-private-sentinel' not in process.stdout + process.stderr
    return json.loads(process.stdout)


def unchanged(s, before=None):
    for path, content in s.inputs.items():
        assert path.read_bytes() == content
    assert stat.S_IMODE(s.values.stat().st_mode) == 0o640
    if before is not None:
        assert s.values.read_bytes() == before


def read_values(s):
    return json.loads(s.values.read_text(encoding='utf-8'))


def same_scalars(actual, expected):
    assert actual == expected
    assert all(type(actual[key]) is type(value) for key, value in expected.items())


def success(payload, s, *, changed=True):
    values = read_values(s)
    port = values['HTTP_PORT']
    assert type(port) is int and 0 < port <= 65535
    expected = fixture('parameters.json')
    expected.update(HTTP_PORT=port, BASE_URL=f'http://127.0.0.1:{port}',
                    CALLBACK_URL=f'http://127.0.0.1:{port}/callback')
    same_scalars(values, expected)
    expected_result = fixture('success.json')
    expected_result['requirements'][0]['result']['network']['ports']['HTTP_PORT'] = port
    expected_result['requirements'][0]['result']['network']['changed'] = changed
    assert payload == expected_result
    assert payload['requirements'][0]['result']['network']['changed'] is changed
    unchanged(s)
    return port


def diagnostic(error, contexts, cause):
    assert isinstance(error, str) and error.strip()
    assert any(context in error for context in contexts), 'Identify the affected declaration or file'
    assert any(re.search(pattern, error, re.IGNORECASE)
               for pattern in fixture('diagnostic-causes.json')[cause]), 'Explain the observed cause'
    assert re.search(r'(?:\b(?:start-app|environment-maintenance)\s+adjust\b|'
                     r'-m\s+environment_maintenance\s+adjust\b)', error), 'Give an executable continuation'


def failure(process, s, code, before, ids=('connections',), *, contexts, cause):
    payload = response(process, 1)
    error = payload['error']
    diagnostic(error, contexts, cause)
    expected = fixture('failure.json')
    row = expected['requirements'][0]
    expected['requirements'] = []
    expected['error'] = error
    for identity in ids:
        item = deepcopy(row)
        item['id'] = identity
        item['result']['error'] = error
        item['result']['network']['error_code'] = code
        expected['requirements'].append(item)
    assert payload == expected
    assert all(item['result']['network']['changed'] is False for item in payload['requirements'])
    unchanged(s, before)


@contextmanager
def owned_server(port=0, marker='first-instance'):
    argv = [sys.executable, '-u', '-B', str(DATA / 'http_server.py'), str(port), marker]
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ready = b''
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(5), 'Test-owned HTTP server failed to become ready'
        ready = process.stdout.readline()
        assert ready, 'Test-owned HTTP server exited before readiness'
        identity = json.loads(ready)
        assert identity['pid'] == process.pid and process.poll() is None
        assert type(identity['port']) is int and identity['port'] > 0
        yield SimpleNamespace(process=process, port=identity['port'], pid=process.pid,
            start_ticks=identity['start_ticks'], marker=(marker + '\n').encode())
    finally:
        if process.poll() is None:
            process.terminate()
        output, errors = process.communicate(timeout=5)
        record(dict(kind='http-process', argv=argv, pid=process.pid, exit_code=process.returncode,
                    stdout=(ready + output).decode('utf-8'), stderr=errors.decode('utf-8'), reaped=True))
        assert process.poll() is not None


def http(server):
    with urlopen(f'http://127.0.0.1:{server.port}/', timeout=5) as result:
        assert result.status == 200 and result.read() == server.marker
    assert server.process.poll() is None


def seed_port(s, port):
    value = read_values(s)
    value['HTTP_PORT'] = port
    write(s.values, value)


def set_owner(s, pid, ticks):
    value = fixture('adjust.json')
    value['requirements'][0]['network']['ports'][0]['owner'] = dict(pid=pid, start_ticks=ticks)
    profile(s, value)


def can_bind(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind(('127.0.0.1', port))


def test_occupied_port_and_addresses_use_explicit_file_and_two_live_servers(scenario):
    s = scenario
    with owned_server() as first:
        http(first)
        seed_port(s, first.port)
        value = read_values(s)
        del value['CALLBACK_URL']  # Explicitly declared outputs may be created.
        write(s.values, value)
        port = success(response(invoke(s)), s)
        assert port != first.port
        with owned_server(port, 'second-instance') as second:
            http(second)
            http(first)


def test_all_selected_network_rows_publish_once_in_selection_order(scenario, monkeypatch):
    s = scenario
    multi(s)
    calls = []
    original = os.replace

    def replace(source, target):
        if Path(target) == s.values:
            planned = json.loads(Path(source).read_text(encoding='utf-8'))
            for key in ('HTTP_PORT', 'ADMIN_PORT'):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as competitor:
                    with pytest.raises(OSError) as occupied:
                        competitor.bind(('127.0.0.1', planned[key]))
                    assert occupied.value.errno == errno.EADDRINUSE
        calls.append((Path(source), Path(target)))
        return original(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(os, 'replace', replace)
        payload = response(invoke_here(s, '["admin","http"]'))
    values = read_values(s)
    http_port, admin_port = values['HTTP_PORT'], values['ADMIN_PORT']
    assert type(http_port) is type(admin_port) is int
    assert 0 < http_port <= 65535 and 0 < admin_port <= 65535 and http_port != admin_port
    expected = fixture('multi-parameters.json')
    expected.update(HTTP_PORT=http_port, ADMIN_PORT=admin_port,
        BASE_URL=f'http://127.0.0.1:{http_port}',
        CALLBACK_URL=f'http://127.0.0.1:{http_port}/callback',
        ADMIN_URL=f'http://127.0.0.1:{admin_port}/admin')
    same_scalars(values, expected)
    expected_result = fixture('multi-success.json')
    expected_result['requirements'][0]['result']['network']['ports']['ADMIN_PORT'] = admin_port
    expected_result['requirements'][1]['result']['network']['ports']['HTTP_PORT'] = http_port
    assert payload == expected_result
    assert all(row['result']['network']['changed'] is True for row in payload['requirements'])
    assert len(calls) == 1 and calls[0][1] == s.values
    assert not calls[0][0].exists()
    unchanged(s)
    with owned_server(http_port, 'http-instance') as http_instance:
        with owned_server(admin_port, 'admin-instance') as admin_instance:
            http(http_instance)
            http(admin_instance)


def test_free_and_confirmed_own_repeat_keep_file_and_skip_publication(scenario, monkeypatch):
    s = scenario
    port = success(response(invoke(s)), s)
    before = s.values.read_bytes()
    calls = []
    original = os.replace

    def replace(source, target):
        calls.append((source, target))
        return original(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(os, 'replace', replace)
        assert success(response(invoke_here(s)), s, changed=False) == port
    unchanged(s, before)
    assert calls == []
    with owned_server(port, 'owned-instance') as own:
        set_owner(s, own.pid, own.start_ticks)
        with monkeypatch.context() as patch:
            patch.setattr(os, 'replace', replace)
            assert success(response(invoke_here(s)), s, changed=False) == port
        unchanged(s, before)
        assert calls == []
        http(own)


@pytest.mark.parametrize('kind', ['wrong-start', 'pid-without-listener'])
def test_claimed_owner_requires_matching_process_identity_and_listener(scenario, kind):
    s = scenario
    with owned_server() as first, owned_server(marker='other-live-process') as other:
        seed_port(s, first.port)
        if kind == 'wrong-start':
            set_owner(s, first.pid, str(int(first.start_ticks) + 1))
        else:
            set_owner(s, other.pid, other.start_ticks)
        before = s.values.read_bytes()
        failure(invoke(s), s, 'ownership_mismatch', before,
                contexts=('HTTP_PORT', 'connections'), cause=kind)
        http(first)
        http(other)


def test_unreadable_declared_process_evidence_is_not_foreign_allocation(scenario, monkeypatch):
    s = scenario
    with owned_server() as own:
        seed_port(s, own.port)
        set_owner(s, own.pid, own.start_ticks)
        before = s.values.read_bytes()
        prefix = f'/proc/{own.pid}'

        def denying(original):
            def call(path, *args, **kwargs):
                if not isinstance(path, int):
                    name = os.fsdecode(path)
                    if name == prefix or name.startswith(prefix + '/'):
                        raise PermissionError(errno.EACCES, 'test-owned evidence refusal', name)
                return original(path, *args, **kwargs)
            return call

        with monkeypatch.context() as patch:
            for owner, names in ((builtins, ('open',)), (io, ('open',)),
                    (os, ('open', 'stat', 'listdir', 'scandir', 'readlink'))):
                for name in names:
                    patch.setattr(owner, name, denying(getattr(owner, name)))
            process = invoke_here(s)
        failure(process, s, 'ownership_unavailable', before,
                contexts=('HTTP_PORT', 'connections'), cause='unavailable')
        http(own)


def test_later_reservation_failure_preserves_file_and_releases_siblings(scenario, monkeypatch):
    s = scenario
    multi(s)
    before = s.values.read_bytes()
    held, ports, refused = [], [], []
    original = socket.socket.bind

    def bind(candidate, address):
        if address == ('127.0.0.1', 0):
            if any(item.fileno() >= 0 for item in held):
                refused.append(True)
                raise OSError(errno.ENOBUFS, 'test-owned replacement allocation refusal')
            answer = original(candidate, address)
            held.append(candidate)
            ports.append(candidate.getsockname()[1])
            return answer
        return original(candidate, address)

    with owned_server() as unrelated:
        try:
            with monkeypatch.context() as patch:
                patch.setattr(socket.socket, 'bind', bind)
                process = invoke_here(s)
            failure(process, s, 'allocation_failed', before, ids=('http', 'admin'),
                    contexts=('ADMIN_PORT', 'admin'), cause='allocation')
            assert refused and ports, 'Fault must occur with an actual sibling reservation held'
            assert all(candidate.fileno() == -1 for candidate in held)
            for port in ports:
                can_bind(port)
            http(unrelated)
        finally:
            # Check the subject's cleanup above, then contain even a failing implementation.
            for candidate in held:
                candidate.close()


def test_atomic_replace_failure_retains_bytes_mode_and_cleans_staging(scenario, monkeypatch):
    s = scenario
    with owned_server() as first:
        seed_port(s, first.port)
        before = s.values.read_bytes()
        existing_files = set(s.values.parent.iterdir())
        candidates = []
        reservations = []
        original = os.replace
        original_bind = socket.socket.bind

        def bind(candidate, address):
            answer = original_bind(candidate, address)
            reservations.append(candidate)
            return answer

        def refuse(source, target):
            if Path(target) == s.values:
                planned = json.loads(Path(source).read_text(encoding='utf-8'))
                candidates.append((Path(source), planned))
                assert any(candidate.fileno() >= 0
                           and candidate.getsockname()[1] == planned['HTTP_PORT']
                           for candidate in reservations), 'Hold the reservation through publication'
                raise OSError(errno.EACCES, 'test-owned publication refusal')
            return original(source, target)

        try:
            with monkeypatch.context() as patch:
                patch.setattr(os, 'replace', refuse)
                patch.setattr(socket.socket, 'bind', bind)
                process = invoke_here(s)
            failure(process, s, 'write_failed', before, contexts=(str(s.values),), cause='write')
            assert len(candidates) == 1
            temporary, value = candidates[0]
            port = value['HTTP_PORT']
            assert type(port) is int and 0 < port <= 65535 and port != first.port
            assert value['BASE_URL'] == f'http://127.0.0.1:{port}'
            assert value['CALLBACK_URL'] == f'http://127.0.0.1:{port}/callback'
            assert all(candidate.fileno() == -1 for candidate in reservations)
            assert not temporary.exists() and set(s.values.parent.iterdir()) == existing_files
            can_bind(port)
            http(first)
        finally:
            for candidate in reservations:
                candidate.close()


def initial_free_port():
    # Arrange an observed initial value, never predict the allocator's replacement.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind(('127.0.0.1', 0))
        return candidate.getsockname()[1]


def legacy_inputs(s):
    value = fixture('main.json')
    value['interpreters']['exit'] = dict(module='network_adjustment_interpreter', attribute='exit_result')
    write(s.main, value)
    s.inputs[s.main] = s.main.read_bytes()
    value = read_values(s)
    value.update(python=sys.executable, probe=str(DATA / 'trace.py'), trace=str(s.trace))
    write(s.values, value)


def preflight(s, monkeypatch, field):
    before = s.values.read_bytes()
    binds, publications = [], []
    original_bind, original_replace = socket.socket.bind, os.replace

    def bind(candidate, address):
        binds.append(address)
        return original_bind(candidate, address)

    def replace(source, target):
        publications.append(target)
        return original_replace(source, target)

    with monkeypatch.context() as patch:
        patch.syspath_prepend(str(DATA))
        patch.setattr(socket.socket, 'bind', bind)
        patch.setattr(os, 'replace', replace)
        process = invoke_here(s)
    assert process.returncode == 2 and process.stdout == b''
    assert b'network' in process.stderr and field.encode() in process.stderr
    assert SECRET.encode() not in process.stderr
    assert binds == [] and publications == []
    assert not s.trace.exists()
    unchanged(s, before)
    return process


@pytest.mark.parametrize('case', fixture('invalid.json'), ids=lambda case: case['id'])
def test_network_preflight_refuses_known_invalid_fields_without_effects(scenario, monkeypatch, case):
    s = scenario
    if case.get('positive_port'):
        seed_port(s, initial_free_port())
    if case.get('with_commands'):
        legacy_inputs(s)
    value = read_values(s) if case['target'] == 'parameters' else fixture('adjust.json')
    if case.get('with_commands'):
        value['requirements'][0]['commands'] = [fixture('command.json')]
    position = value
    for key in case['path'][:-1]:
        position = position[key]
    if case.get('delete'):
        del position[case['path'][-1]]
    else:
        position[case['path'][-1]] = case['value']
    if case['target'] == 'parameters':
        write(s.values, value)
    else:
        profile(s, value)
    process = preflight(s, monkeypatch, case['field'])
    assert re.search(case['correction'], process.stderr.decode(), re.IGNORECASE), 'Explain a corrective value or selection'


@pytest.mark.parametrize('same_row', [True, False], ids=['same-row', 'mixed-selection'])
def test_mixed_network_and_commands_refused_before_trace_command(scenario, monkeypatch, same_row):
    s = scenario
    document = fixture('adjust.json')
    command = fixture('command.json')
    if same_row:
        document['requirements'][0]['commands'] = [command]
    else:
        document['requirements'].insert(0, dict(id='legacy', commands=[command]))
    profile(s, document)
    legacy_inputs(s)
    process = preflight(s, monkeypatch, 'adjust')
    assert '--requirements' in process.stderr.decode()


def test_initial_free_positive_port_kept_while_stale_addresses_repaired(scenario):
    s = scenario
    initial = initial_free_port()
    seed_port(s, initial)
    assert read_values(s)['BASE_URL'] != f'http://127.0.0.1:{initial}'
    assert success(response(invoke(s)), s) == initial
    with owned_server(initial, 'retained-free-port') as server:
        http(server)


def test_terminated_owner_is_mismatch_and_preserves_configuration(scenario):
    s = scenario
    with owned_server() as former:
        seed_port(s, former.port)
        set_owner(s, former.pid, former.start_ticks)
    assert former.process.poll() is not None
    assert not Path(f'/proc/{former.pid}').exists(), 'The fixture needs an absent, reaped PID'
    before = s.values.read_bytes()
    failure(invoke(s), s, 'ownership_mismatch', before,
            contexts=('HTTP_PORT', 'connections'), cause='dead-owner')


@pytest.mark.parametrize('kind', ['ports-only', 'new-output'])
def test_valid_address_shapes_and_unknown_metadata_preserved(scenario, kind):
    s = scenario
    document = fixture('valid-adjust.json')
    if kind == 'ports-only':
        document['requirements'][0]['network']['addresses'] = {}
    profile(s, document)
    write(s.values, fixture('valid-parameters.json'))
    assert 'HEALTH_URL' not in read_values(s)
    payload = response(invoke(s))
    values = read_values(s)
    port = values['HTTP_PORT']
    assert type(port) is int and 0 < port <= 65535
    expected = fixture('valid-parameters.json')
    expected['HTTP_PORT'] = port
    if kind == 'new-output':
        expected.update(BASE_URL=f'http://127.0.0.1:{port}',
                        CALLBACK_URL=f'http://127.0.0.1:{port}/callback',
                        HEALTH_URL=f'http://127.0.0.1:{port}/health')
    same_scalars(values, expected)
    expected_result = fixture(kind + '-success.json')
    expected_result['requirements'][0]['result']['network']['ports']['HTTP_PORT'] = port
    assert payload == expected_result
    assert payload['requirements'][0]['result']['network']['changed'] is True
    unchanged(s)
    can_bind(port)


def test_empty_network_selection_has_no_effects(scenario):
    s = scenario
    before = s.values.read_bytes()
    assert response(invoke(s, '[]')) == dict(operation='adjust', status='succeeded',
                                             requirements=[], error=None)
    unchanged(s, before)


def test_dictionary_api_never_guesses_a_network_publication_path(scenario):
    s = scenario
    before = s.values.read_bytes()
    parameters = read_values(s)
    snapshot = deepcopy(parameters)
    with pytest.raises(ValueError):
        prepare_resources(s.main, 'adjust', 'all', parameters,
                          base_dir=s.home, interpreters={})
    same_scalars(parameters, snapshot)
    unchanged(s, before)
