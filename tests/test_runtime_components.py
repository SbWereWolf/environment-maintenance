"""Installed runtime behavior remains available without the example directory."""
from contextlib import contextmanager
import json

import pytest

from run_stop_support import FIXTURES, Lab
from npm_delivery_support import living_group
from test_npm_persistent_entry import package, consumer


@contextmanager
def unavailable_examples(consumer, tmp_path):
    examples = consumer.python.parent.parent.parent / 'examples'
    parked = tmp_path / 'unavailable-examples'
    assert examples.is_dir(), 'Expected actual npm package contents before isolation'
    examples.rename(parked)
    try:
        assert not examples.exists()
        yield
    finally:
        parked.rename(examples)


def test_actual_installed_runtime_control(package, consumer, tmp_path):
    probe = ('import environment_maintenance,sys; from pathlib import Path; '
             'assert Path(environment_maintenance.__file__).is_relative_to(Path(sys.prefix)); '
             'print(environment_maintenance.__version__)')
    result = package.capture('runtime-identity', [consumer.python, '-I', '-B', '-c', probe], tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == b'4.0.0'
    assert result.stderr == b''


@pytest.mark.parametrize('code,accepted,success', [(0, 0, True), (7, 0, False),
                                                (7, 7, True), (0, 7, False)])
def test_installed_interpreter_respects_declared_exit_codes_without_examples(
        package, consumer, tmp_path, code, accepted, success):
    with unavailable_examples(consumer, tmp_path):
        result = package.capture('runtime-interpreter', [consumer.python, '-I', '-B',
            FIXTURES / 'runtime_interpreter_probe.py', code, accepted], tmp_path)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert result.stderr == b''
    answer = json.loads(result.stdout)
    assert answer['success'] is success
    assert type(answer['value']) is int and answer['value'] == code
    if success:
        assert answer['error'] is None
    else:
        assert isinstance(answer['error'], str) and answer['error']


def test_installed_console_submits_group_without_examples(package, consumer, tmp_path):
    lab = Lab(tmp_path / 'owned-launch')
    out, err = lab.root / 'stdout.log', lab.root / 'stderr.log'
    try:
        with unavailable_examples(consumer, tmp_path):
            result = package.capture('runtime-console', [consumer.python, '-I', '-B', '-m',
                'environment_maintenance.running.console', '--stdout-log', out,
                '--stderr-log', err, '--', consumer.python, '-I', '-B',
                FIXTURES / 'worker.py', lab.root, 'installed'], lab.root)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        assert result.stderr == b''
        answer = json.loads(result.stdout)
        assert answer['status'] == 'submitted'
        assert type(answer['pgid']) is int and answer['pgid'] > 0
        lab.terminal_groups.append(answer['pgid'])
        observed = lab.started('installed')
        assert observed['pid'] == observed['pgid'] == answer['pgid']
        assert living_group(answer['pgid']) == [observed['pid']]
        assert out.is_file() and err.is_file()
    finally:
        lab.close()
