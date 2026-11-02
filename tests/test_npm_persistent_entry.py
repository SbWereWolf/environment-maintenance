"""PK03–PK06: actual npm entries, independent effects and preserved instances."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from npm_delivery_support import PackageLab, fixture, write_json
from test_npm_delivery import assert_action, assert_json_equal


@pytest.fixture(scope='module')
def package():
    lab = PackageLab()
    try:
        yield lab
    finally:
        lab.close()


@pytest.fixture(scope='module')
def consumer(package):
    installed = package.install('ordinary')
    package.require_consumer(installed)
    return installed


def ordinary_profile(package, consumer, directory, token='chosen-token-Ω'):
    profile = package.scenario(directory, consumer)
    profile.consumer = consumer
    profile.package_root = consumer.python.parent.parent.parent
    profile.ordinary = directory / 'start-app.json'
    profile.ordinary_values = directory / 'start-app-values.json'
    profile.data = directory / 'retained-data.txt'
    profile.data.write_text('Retain application data\n', encoding='utf-8')
    profile.data.chmod(0o600)
    values = dict(profile.parameters, token=token)
    write_json(profile.ordinary_values, values)
    main = fixture('main.json')
    main['operations'] = {operation: str(path) for operation, path in profile.documents.items()}
    main['invocation'] = dict(parameters='start-app-values.json', base_dir=str(profile.serviced),
        requirements={operation: ['selected'] for operation in ('infra', 'deps', 'adjust', 'run')})
    write_json(profile.ordinary, main)
    profile.ordinary.chmod(0o640)
    profile.ordinary_values.chmod(0o640)
    probe = ('import json,environment_maintenance,jsonpatch,jsonpointer; '
             'print(json.dumps({m.__name__:m.__file__ for m in '
             '(environment_maintenance,jsonpatch,jsonpointer)}))')
    identity = package.capture('setup-module-paths',
        [consumer.python, '-I', '-B', '-c', probe], directory)
    assert identity.returncode == 0 and identity.stderr == b''
    profile.modules = json.loads(identity.stdout)
    return profile


def protected(profile):
    paths = [profile.ordinary, profile.ordinary_values, profile.data,
             profile.consumer.entry, profile.consumer.python, *profile.documents.values()]
    paths += [Path(path) for path in profile.modules.values()]
    paths += [Path(profile.modules['environment_maintenance']).parent / name
              for name in ('cli.py', 'invocation.py')]
    return {str(path): (hashlib.sha256(path.read_bytes()).hexdigest(),
                        path.stat().st_mode & 0o777) for path in paths if path.exists()}


def invoke(package, profile, operation, form, *arguments, cwd=None, identity=False):
    if form == 'local':
        entry, selected_cwd = 'start-app', profile.directory
    else:
        entry, selected_cwd = profile.consumer.entry, cwd or profile.directory
    environment = dict(package.env, PYTHONPATH=str(profile.plugins))
    environment['PATH'] = str(profile.consumer.entry.parent) + os.pathsep + package.env['PATH']
    if identity:
        environment['NPM_TEST_ENTRY_IDENTITY'] = '1'
    return package.capture('ordinary-' + operation + '-' + form,
        [entry, operation, *arguments], selected_cwd, env=environment, timeout=20)


def answer(completed, operation):
    assert completed.returncode == 0, completed.stderr.decode(errors='replace')
    assert completed.stderr == b''
    value = json.loads(completed.stdout)
    assert value['operation'] == operation
    assert value['status'] == 'succeeded' and value['error'] is None
    return value


def actions(result):
    if result['operation'] == 'check':
        return [row['presence'] for row in result['resources']] + [
            row['result'] for row in result['checks']]
    return [row['result'] for row in result['requirements']]


def assert_effects(result, profile, operation, token='chosen-token-Ω'):
    labels = ['infra', 'deps', 'check'] if operation == 'check' else [operation]
    if operation == 'check':
        assert [row['operation'] for row in result['resources']] == ['infra', 'deps']
        assert [row['id'] for row in result['resources']] == ['selected', 'selected']
        assert [row['id'] for row in result['checks']] == ['selected']
    else:
        assert [row['id'] for row in result['requirements']] == ['selected']
    expected = []
    for label in labels:
        row = fixture('event.json')
        row.update(label=label, cwd=str(profile.serviced), token=token, only=token)
        expected.append(row)
    observed = [json.loads(line) for line in profile.events.read_text().splitlines()]
    assert_json_equal(observed, expected)
    for action, label in zip(actions(result), labels, strict=True):
        assert action['status'] == 'succeeded' and action['error'] is None
        assert len(action['commands']) == 1
        record = action['commands'][0]
        assert record['exit_code'] == 0 and record['error'] is None
        assert record['invocation'] == dict(argv=[str(profile.consumer.python), '-B',
            str(profile.directory / 'probe.py'), str(profile.events), label, token,
            'argument with spaces Ω'], cwd=str(profile.serviced), env=dict(ONLY_ENV=token))


def assert_engine(result, profile):
    for action in actions(result):
        for record in action['commands']:
            identity = record['interpretation']['value']['identity']
            assert identity['executable'] == str(profile.consumer.python)
            assert identity['prefix'] == str(profile.consumer.python.parent.parent)
            assert identity['version'] == identity['metadata']
            assert identity['modules'] == profile.modules
            assert type(identity['pid']) is int and identity['pid'] > 0
            assert all(Path(path).is_relative_to(profile.consumer.prefix)
                       for path in identity['modules'].values())


@pytest.mark.parametrize('operation', ['infra', 'deps', 'adjust', 'check', 'run'])
@pytest.mark.parametrize('form', ['local', 'absolute'])
def test_all_five_operations_use_both_real_short_entry_forms(package, consumer, tmp_path,
                                                          operation, form):
    profile = ordinary_profile(package, consumer, tmp_path / 'inputs')
    before = protected(profile)
    explicit = ['--config', profile.ordinary, '--parameters', profile.ordinary_values,
                '--base-dir', profile.serviced]
    if operation != 'check':
        explicit += ['--requirements', '["selected"]']
    control = answer(invoke(package, profile, operation, form, *explicit), operation)
    assert_effects(control, profile, operation)
    assert protected(profile) == before
    profile.events.unlink()
    result = answer(invoke(package, profile, operation, form), operation)
    assert_effects(result, profile, operation)
    labels = ['infra', 'deps', 'check'] if operation == 'check' else [operation]
    for action, label in zip(actions(result), labels, strict=True):
        assert_action(action, profile, label, fixture('stream-profile.json'))
    assert protected(profile) == before


def test_relative_parameter_override_is_one_call_across_npm_boundary(package, consumer, tmp_path):
    profile = ordinary_profile(package, consumer, tmp_path / 'inputs')
    caller = tmp_path / 'foreign caller'
    caller.mkdir()
    override = caller / 'chosen.json'
    write_json(override, dict(profile.parameters, token='override-token-Ω'))
    override_before = override.read_bytes(), override.stat().st_mode & 0o777
    before = protected(profile)
    result = answer(invoke(package, profile, 'deps', 'absolute', '--config', profile.ordinary, '--parameters',
        'chosen.json', cwd=caller), 'deps')
    assert_effects(result, profile, 'deps', 'override-token-Ω')
    assert protected(profile) == before
    profile.events.unlink()
    result = answer(invoke(package, profile, 'deps', 'absolute'), 'deps')
    assert_effects(result, profile, 'deps')
    assert protected(profile) == before
    assert (override.read_bytes(), override.stat().st_mode & 0o777) == override_before


def test_relative_main_override_anchors_defaults_at_main_without_persisting(package, consumer,
                                                                         tmp_path):
    profile = ordinary_profile(package, consumer, tmp_path / 'inputs')
    caller = tmp_path / 'foreign caller'
    selected = caller / 'profiles'
    selected.mkdir(parents=True)
    main = json.loads(profile.ordinary.read_text())
    main['invocation']['parameters'] = 'selected-values.json'
    # Different declared main directory; the relative serviced cwd is inside it.
    serviced = selected / 'serviced cwd Ω'
    serviced.mkdir()
    main['invocation']['base_dir'] = 'serviced cwd Ω'
    write_json(selected / 'alternate.json', main)
    write_json(selected / 'selected-values.json', dict(profile.parameters,
        token='main-token-Ω', serviced=str(serviced)))
    write_json(caller / 'selected-values.json', dict(profile.parameters, token='caller-decoy'))
    extra = [selected / 'alternate.json', selected / 'selected-values.json',
             caller / 'selected-values.json']
    extra_before = {str(path): (path.read_bytes(), path.stat().st_mode & 0o777) for path in extra}
    before = protected(profile)
    result = answer(invoke(package, profile, 'deps', 'absolute', '--config',
        'profiles/alternate.json', cwd=caller), 'deps')
    expected = fixture('event.json')
    expected.update(label='deps', cwd=str(serviced), token='main-token-Ω', only='main-token-Ω')
    assert_json_equal([json.loads(line) for line in profile.events.read_text().splitlines()], [expected])
    assert [row['id'] for row in result['requirements']] == ['selected']
    assert protected(profile) == before
    profile.events.unlink()
    result = answer(invoke(package, profile, 'deps', 'absolute'), 'deps')
    assert_effects(result, profile, 'deps')
    assert protected(profile) == before
    assert {str(path): (path.read_bytes(), path.stat().st_mode & 0o777) for path in extra} == extra_before


def test_two_real_npm_instances_select_own_engine_and_preserve_other(package, consumer, tmp_path):
    second = package.install('second ordinary')
    package.require_consumer(second)
    a = ordinary_profile(package, consumer, tmp_path / 'A', token='A-token-Ω')
    b = ordinary_profile(package, second, tmp_path / 'B', token='B-token-Ω')
    before_b = protected(b)
    before_a = protected(a)
    result = answer(invoke(package, a, 'run', 'absolute', identity=True), 'run')
    assert_engine(result, a)
    assert_effects(result, a, 'run', 'A-token-Ω')
    assert not b.events.exists() and protected(b) == before_b
    assert protected(a) == before_a
    a_events_before_b = a.events.read_bytes()
    result = answer(invoke(package, b, 'run', 'local', identity=True), 'run')
    assert_engine(result, b)
    assert_effects(result, b, 'run', 'B-token-Ω')
    assert protected(a) == before_a and protected(b) == before_b
    assert a.events.read_bytes() == a_events_before_b
    assert a.modules != b.modules


def test_missing_ordinary_main_has_installation_diagnostic_and_no_effects(package, consumer,
                                                                       tmp_path):
    profile = ordinary_profile(package, consumer, tmp_path / 'inputs')
    profile.ordinary.unlink()
    before = protected(profile)
    result = invoke(package, profile, 'infra', 'absolute')
    assert result.returncode == 2 and str(profile.ordinary).encode() in result.stderr
    assert result.stdout == b''
    assert not profile.events.exists() and protected(profile) == before
