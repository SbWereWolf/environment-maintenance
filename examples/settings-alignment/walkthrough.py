"""Корректные примеры согласования на собственных временных копиях конфигурации."""
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from environment_maintenance import prepare_resources


ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / 'examples/settings-alignment'
TOOL = SAMPLES / 'align_queue.py'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def prepare_demo(workspace):
    """Подготовить собственные копии, явные значения и готовый обработчик примера."""
    for path in SAMPLES.glob('*.example.json'):
        shutil.copyfile(path, workspace / path.name)
    parameters_path = workspace / 'parameters.example.json'
    parameters = json.loads(parameters_path.read_text(encoding='utf-8'))
    parameters.update(python=sys.executable, tool=str(TOOL),
        settings_config=str(workspace / 'settings.example.json'), source_path=str(ROOT / 'src'))
    parameters_path.write_text(json.dumps(parameters, ensure_ascii=False), encoding='utf-8')
    registry = {'result': runpy.run_path(
        str(ROOT / 'examples/resource-preparation/interpreters.py'))['exit_result']}
    before = json.loads((workspace / 'applications.example.json').read_text(encoding='utf-8'))
    return workspace / 'app.example.json', parameters, registry, before


def assert_settings(workspace, before, variable, queue):
    expected = deepcopy(before)
    expected['requirements'][0]['commands'][0]['env'][variable] = queue
    expected['requirements'][2]['commands'][0]['env'][variable] = queue
    actual = json.loads((workspace / 'applications.example.json').read_text(encoding='utf-8'))
    assert canonical(actual) == canonical(expected)


def assert_result(result, *, encoded):
    assert result['operation'] == 'adjust' and result['status'] == 'succeeded'
    assert result['error'] is None
    assert [r['id'] for r in result['requirements']] == ['queue-agreement']
    action = result['requirements'][0]['result']
    assert action['status'] == 'succeeded' and action['error'] is None
    assert len(action['commands']) == 1
    command = action['commands'][0]
    assert command['exit_code'] == 0 and command['error'] is None
    stdout, stderr = command['stdout'], command['stderr']
    if encoded:
        stdout = base64.b64decode(stdout['data'], validate=True)
        stderr = base64.b64decode(stderr['data'], validate=True)
    assert stderr == b'' and stdout.endswith(b'\n') and len(stdout.splitlines()) == 1
    assert json.loads(stdout) == dict(status='succeeded', writer='writer', reader='reader',
                                     variable='QUEUE_NAME', queue='billing.jobs')


def run_cli(workspace, selection):
    return subprocess.run([sys.executable, '-B', '-m', 'environment_maintenance', 'adjust',
        '--config', str(workspace / 'app.example.json'),
        '--parameters', str(workspace / 'parameters.example.json'),
        '--base-dir', str(workspace), '--requirements', selection],
        cwd=workspace, env=dict(os.environ, PYTHONPATH=os.pathsep.join((
            str(ROOT / 'src'), str(ROOT / 'examples/resource-preparation')))), capture_output=True)


def main():
    originals = {path: path.read_bytes() for path in SAMPLES.glob('*.example.json')}
    with TemporaryDirectory(prefix='alignment-api-') as temporary:
        workspace = Path(temporary)
        config, parameters, registry, before = prepare_demo(workspace)
        result = prepare_resources(config, 'adjust', 'all', parameters,
                                   base_dir=workspace, interpreters=registry)
        assert_result(result, encoded=False)
        assert_settings(workspace, before, 'QUEUE_NAME', 'billing.jobs')
        print('api adjust: selected values confirmed; other settings preserved')
    with TemporaryDirectory(prefix='alignment-cli-') as temporary:
        workspace = Path(temporary)
        _, _, _, before = prepare_demo(workspace)
        process = run_cli(workspace, '["queue-agreement"]')
        assert process.returncode == 0 and process.stderr == b''
        assert_result(json.loads(process.stdout), encoded=True)
        assert_settings(workspace, before, 'QUEUE_NAME', 'billing.jobs')
        print('cli adjust: selected requirement; complete result')
    with TemporaryDirectory(prefix='alignment-empty-') as temporary:
        workspace = Path(temporary)
        prepare_demo(workspace)
        target = workspace / 'applications.example.json'
        before = target.read_bytes()
        process = run_cli(workspace, '[]')
        assert process.returncode == 0 and process.stderr == b''
        assert json.loads(process.stdout) == dict(operation='adjust', status='succeeded',
                                                 requirements=[], error=None)
        assert target.read_bytes() == before
        print('selection: empty succeeds without writes')
    with TemporaryDirectory(prefix='alignment-tool-') as temporary:
        workspace = Path(temporary)
        _, _, _, before = prepare_demo(workspace)
        process = subprocess.run([sys.executable, '-B', str(TOOL),
            '--config', str(workspace / 'settings.example.json'), '--operation', 'applications',
            '--writer', 'writer', '--reader', 'reader', '--queue-variable', 'OTHER_QUEUE',
            '--queue', 'archive.jobs'], cwd=workspace,
            env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), capture_output=True)
        assert process.returncode == 0 and process.stderr == b''
        assert json.loads(process.stdout) == dict(status='succeeded', writer='writer', reader='reader',
            variable='OTHER_QUEUE', queue='archive.jobs')
        assert_settings(workspace, before, 'OTHER_QUEUE', 'archive.jobs')
        print('tool: selected variable; confirmed values')
    for path, raw in originals.items():
        assert path.read_bytes() == raw


if __name__ == '__main__':
    main()
