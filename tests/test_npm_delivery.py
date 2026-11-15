"""C01–C13: external npm delivery with independent data and actual consumers."""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tomllib

import pytest

from npm_delivery_support import FIXTURES, ROOT, PackageLab, fixture, write_json


CANDIDATE_VERSION = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']


@pytest.fixture(scope='module')
def package():
    lab = PackageLab()
    try:
        yield lab
    finally:
        lab.close()


@pytest.fixture(scope='module')
def consumer(package):
    return package.install('positive')


@pytest.fixture
def scenario(package, consumer, tmp_path):
    if not package.available:
        return None
    return package.scenario(tmp_path / 'consumer inputs', consumer)


def require(package, consumer):
    package.require_consumer(consumer)


def command_result(answer):
    return answer['requirements'][0]['result']['commands'][0]


def events(scenario):
    return [json.loads(line) for line in scenario.events.read_text().splitlines()]


def assert_json_equal(actual, expected):
    options = dict(ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    assert json.dumps(actual, **options) == json.dumps(expected, **options)


def assert_entry_identity(identity, prefix):
    assert identity['version'] == identity['metadata'] == CANDIDATE_VERSION
    assert type(identity['pid']) is int and identity['pid'] > 0
    assert Path(identity['executable']).is_relative_to(prefix)
    assert Path(identity['prefix']).is_relative_to(prefix)
    assert set(identity['modules']) == {'environment_maintenance', 'jsonpatch', 'jsonpointer'}
    for path in identity['modules'].values():
        assert Path(path).is_relative_to(prefix)
        assert not Path(path).is_relative_to(ROOT)


def assert_action(action, scenario, label, profile):
    keys = fixture('action-keys.json')
    assert sorted(action) == keys['result']
    assert action['status'] == 'succeeded' and action['error'] is None
    assert len(action['commands']) == 1
    command = action['commands'][0]
    assert sorted(command) == keys['command']
    assert type(command['exit_code']) is int and command['exit_code'] == 0 and command['error'] is None
    assert_json_equal(command['interpreter'], dict(name='chosen', options=dict(accept=[0])))
    assert sorted(command['invocation']) == keys['invocation']
    assert command['invocation']['argv'] == [scenario.parameters['python'], '-B',
        str(scenario.directory / 'probe.py'), str(scenario.events), label,
        'chosen-token-Ω', 'argument with spaces Ω']
    assert command['invocation']['cwd'] == str(scenario.serviced)
    assert command['invocation']['env'] == dict(ONLY_ENV='chosen-token-Ω')
    for field in ('stdout', 'stderr'):
        assert command[field]['encoding'] == 'base64'
        assert base64.b64decode(command[field]['data'], validate=True) == bytes.fromhex(profile[field + '_hex'])
    assert sorted(command['interpretation']) == keys['interpretation']
    assert_json_equal(command['interpretation'], dict(success=True, value=dict(plugin='first', stdin=''), error=None))


def test_candidate_python_metadata_identifies_new_delivery():
    metadata = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert int(metadata['project']['version'].split('.')[0]) > 3, 'The incompatible CLI needs a new major'


def test_archive_provides_version_and_short_command(package):
    package.require_package()
    with tarfile.open(package.archive) as archive:
        metadata = json.load(archive.extractfile('package/package.json'))
        assert metadata['version'] == CANDIDATE_VERSION
        assert 'start-app' in metadata['bin']
        assert archive.getmember('package/' + metadata['bin']['start-app']).isfile()


def test_archive_contains_owned_material_bytes(package):
    package.require_package()
    with tarfile.open(package.archive) as archive:
        for name in fixture('package-members.json'):
            assert archive.extractfile('package/' + name).read() == (ROOT / name).read_bytes()
        skills = [name for name in archive.getnames() if name.endswith('/SKILL.md')]
        assert skills == ['package/.agents/skills/environment-maintenance/SKILL.md']


def test_archive_excludes_working_material_and_runtime(package):
    package.require_package()
    with tarfile.open(package.archive) as archive:
        for member in archive.getnames():
            assert not {'.venv', 'node_modules', 'build', 'dist', '__pycache__', '.git'} & set(Path(member).parts)
            assert not member.endswith(('.pyc', '.log'))


@pytest.mark.parametrize('argument', ['--version', '--help'])
def test_short_entry_from_another_cwd(package, consumer, argument):
    require(package, consumer)
    result = package.capture('short-entry', [consumer.entry, argument], package.root, timeout=20)
    assert result.returncode == 0 and result.stderr == b''
    if argument == '--version':
        assert result.stdout == f'environment-maintenance {CANDIDATE_VERSION}\n'.encode()
    else:
        for name in (b'infra', b'deps', b'adjust', b'check', b'run'):
            assert name in result.stdout


def test_installed_core_libraries_and_metadata_belong_to_instance(package, consumer, scenario):
    require(package, consumer)
    result = package.invoke(consumer, scenario, changes=dict(NPM_TEST_ENTRY_IDENTITY='1'))
    assert result.returncode == 0 and result.stderr == b''
    identity = command_result(json.loads(result.stdout))['interpretation']['value']['identity']
    assert_entry_identity(identity, consumer.prefix)


@pytest.mark.parametrize('operation', ['infra', 'deps', 'adjust', 'check'])
def test_installed_operations_keep_actual_inputs_effects_and_results(package, consumer, scenario, operation):
    require(package, consumer)
    result = package.invoke(consumer, scenario, operation)
    assert result.returncode == 0 and result.stderr == b''
    answer = json.loads(result.stdout)
    assert result.stdout.endswith(b'\n')
    assert answer['operation'] == operation and answer['status'] == 'succeeded' and answer['error'] is None
    labels = ['infra', 'deps', 'check'] if operation == 'check' else [operation]
    observed = events(scenario)
    expected = []
    for label in labels:
        item = fixture('event.json')
        item.update(label=label, cwd=str(scenario.serviced))
        expected.append(item)
    assert_json_equal(observed, expected)
    profile = fixture('stream-profile.json')
    if operation == 'check':
        assert [r['operation'] for r in answer['resources']] == ['infra', 'deps']
        assert [r['id'] for r in answer['checks']] == ['selected']
        for resource, label in zip(answer['resources'], labels):
            assert_json_equal(resource['availability'], dict(status='not_configured', result=None, reason=None))
            assert_action(resource['presence'], scenario, label, profile)
        assert_action(answer['checks'][0]['result'], scenario, 'check', profile)
    else:
        assert [r['id'] for r in answer['requirements']] == ['selected']
        assert_action(answer['requirements'][0]['result'], scenario, operation, profile)


def test_maintenance_document_is_refused_by_named_run(package, consumer, scenario):
    require(package, consumer)
    result = package.capture('refused-maintenance-run',
        [consumer.entry, 'run', '--config', scenario.main,
         '--parameters', scenario.values, '--base-dir', scenario.serviced],
        scenario.serviced)
    assert result.returncode == 2
    answer = json.loads(result.stdout)
    assert answer['operation'] == 'run' and answer['status'] == 'failed'
    assert answer['planned'] == answer['received_pgids'] == 0
    assert answer['applications'] == [] and answer['file_exists'] is False
    assert not Path(answer['file']).exists()
    assert str(scenario.main).encode() in result.stderr
    assert b'applications must be an array' in result.stderr
    assert not scenario.events.exists()


def test_caller_stdin_and_large_raw_streams_survive_entry(package, consumer, scenario):
    require(package, consumer)
    document = json.loads(scenario.documents['infra'].read_text())
    document['requirements'][0]['commands'][0]['argv'][4] = 'stream'
    write_json(scenario.documents['infra'], document)
    profile = fixture('stream-profile.json')
    result = package.invoke(consumer, scenario, input_bytes=profile['input'].encode(),
        changes=dict(NPM_TEST_STDIN='1', NPM_TEST_LARGE_STDERR='1'))
    assert result.returncode == 0
    assert result.stderr == bytes.fromhex(profile['large_stderr_pattern_hex']) * profile['large_stderr_repetitions']
    command = command_result(json.loads(result.stdout))
    assert base64.b64decode(command['stdout']['data'], validate=True) == (
        bytes.fromhex(profile['large_stdout_pattern_hex']) * profile['large_stdout_repetitions'])
    assert_json_equal(command['interpretation']['value'], dict(plugin='first', stdin=profile['input']))


def test_operation_failure_keeps_code_one_and_diagnostics(package, consumer, scenario):
    require(package, consumer)
    document = json.loads(scenario.documents['infra'].read_text())
    document['requirements'][0]['commands'][0]['argv'][4] = 'fail'
    write_json(scenario.documents['infra'], document)
    result = package.invoke(consumer, scenario)
    assert result.returncode == 1 and result.stderr == b''
    answer = json.loads(result.stdout)
    assert answer['status'] == 'failed'
    command = command_result(answer)
    assert type(command['exit_code']) is int and command['exit_code'] == 7
    assert command['interpretation']['error'] == 'consumer action failed'
    assert 'consumer action failed' in answer['error']
    assert base64.b64decode(command['stderr']['data']) == bytes.fromhex(fixture('stream-profile.json')['stderr_hex'])


def test_input_failure_keeps_code_two_and_available_cause(package, consumer, scenario):
    require(package, consumer)
    scenario.values.write_text('{')
    result = package.invoke(consumer, scenario)
    assert result.returncode == 2 and result.stdout == b''
    assert str(scenario.values).encode() in result.stderr


@pytest.mark.parametrize('mode', ['missing', 'unavailable'])
def test_install_refuses_absent_selected_python(package, mode):
    package.require_package()
    if mode == 'missing':
        installed = package.install('missing-python', remove=['ENVIRONMENT_MAINTENANCE_PYTHON'])
        cause = b'ENVIRONMENT_MAINTENANCE_PYTHON'
    else:
        selected = package.root / 'absent selected python Ω'
        installed = package.install('unavailable-python', changes=dict(ENVIRONMENT_MAINTENANCE_PYTHON=str(selected)))
        cause = str(selected).encode()
    assert installed.result.returncode != 0 and cause in installed.result.stderr


def test_venv_failure_stops_installation(package):
    package.require_package()
    selected = package.root / 'failing-python'
    shutil.copyfile(FIXTURES / 'venv_refused.py', selected)
    shutil.copyfile(FIXTURES / 'pip_must_not_run.sh', package.root / 'pip_must_not_run.sh')
    selected.chmod(0o700)
    marker = package.root / 'pip-must-not-run'
    installed = package.install('venv-failure', changes=dict(ENVIRONMENT_MAINTENANCE_PYTHON=str(selected),
        NPM_TEST_PIP_MARKER=str(marker)))
    assert installed.result.returncode != 0
    assert b'NPM-TEST-VENV-REFUSED' in installed.result.stderr
    assert not marker.exists()
    assert not list(installed.prefix.rglob('site-packages/environment_maintenance'))


def test_real_pip_failure_remains_installation_failure(package):
    package.require_package()
    empty = package.root / 'empty wheel index'
    empty.mkdir()
    installed = package.install('pip-failure', changes=dict(PIP_FIND_LINKS=str(empty)))
    assert installed.result.returncode != 0
    assert b'pip' in installed.result.stderr.lower()
    assert any(name in installed.result.stderr.lower() for name in (b'setuptools', b'jsonpatch', b'jsonpointer'))


def test_missing_runtime_does_not_select_foreign_python(package):
    package.require_package()
    installed = package.install('runtime-failure')
    require(package, installed)
    runtime = installed.python.parent.parent
    assert runtime.is_relative_to(installed.prefix)
    shutil.rmtree(runtime)
    result = package.capture('runtime-failure', [installed.entry, '--version'], package.root, timeout=20)
    assert result.returncode != 0 and result.stdout == b''
    assert b'python' in result.stderr.lower()
    assert not list(installed.prefix.rglob('pyvenv.cfg'))


def test_explicit_interpreter_objects_are_interchangeable(package, consumer, scenario):
    require(package, consumer)
    for attribute in ('first', 'second'):
        main = json.loads(scenario.main.read_text())
        main['interpreters']['chosen']['attribute'] = attribute
        write_json(scenario.main, main)
        result = package.invoke(consumer, scenario)
        assert result.returncode == 0 and result.stderr == b''
        assert_json_equal(command_result(json.loads(result.stdout))['interpretation']['value'], dict(plugin=attribute, stdin=''))


def test_installed_public_configuration_round_trip(package, consumer, scenario):
    require(package, consumer)
    result = package.capture('crud', [consumer.python, '-P', '-s', '-B',
        package.tools / 'crud.py', scenario.main], scenario.serviced, timeout=20)
    assert result.returncode == 0 and result.stderr == b''
    assert_json_equal(json.loads(result.stdout), fixture('crud-expected.json'))


def test_npm_uninstall_and_reinstall_same_archive(package):
    package.require_package()
    installed = package.install('lifecycle')
    require(package, installed)
    removed = package.capture('uninstall', ['npm', 'uninstall', '--global', '--prefix',
        installed.prefix, '--no-audit', '--no-fund', package.metadata['name']], package.root)
    assert removed.returncode == 0
    assert not installed.entry.exists()
    assert not list(installed.prefix.rglob('pyvenv.cfg'))
    repeated = package.install('lifecycle')
    require(package, repeated)
    version = package.capture('reinstalled-version', [repeated.entry, '--version'], package.root, timeout=20)
    assert (version.returncode, version.stdout, version.stderr) == (0, f'environment-maintenance {CANDIDATE_VERSION}\n'.encode(), b'')
    assert hashlib.sha256(package.archive.read_bytes()).hexdigest() == package.archive_digest
