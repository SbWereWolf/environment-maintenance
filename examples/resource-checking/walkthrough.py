"""Корректные проверки собственных файлов через принятые API и внешние процессы."""
import base64
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from environment_maintenance import check_resources, clear_requirements, update_requirement


ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / 'examples/resource-checking'
TOOL = SAMPLES / 'check_settings.py'


def prepare_demo(workspace):
    """Создать собственные копии, реальные пути и готовый прежний обработчик."""
    for path in SAMPLES.glob('*.example.json'):
        shutil.copyfile(path, workspace / path.name)
    values_path = workspace / 'parameters.example.json'
    values = json.loads(values_path.read_text(encoding='utf-8'))
    values.update(python=sys.executable, tool=str(TOOL), source_path=str(ROOT / 'src'),
        infra_file=str(workspace / 'applications.example.json'),
        deps_file=str(workspace / 'settings.example.json'),
        settings_config=str(workspace / 'settings.example.json'))
    values_path.write_text(json.dumps(values, ensure_ascii=False), encoding='utf-8')
    registry = {'result': runpy.run_path(
        str(ROOT / 'examples/resource-preparation/interpreters.py'))['exit_result']}
    return workspace / 'app.example.json', values, registry


def snapshot(workspace):
    return {path.name: path.read_bytes() for path in workspace.glob('*.json')}


def assert_result(result, *, encoded, availability=True):
    assert set(result) == {'operation', 'status', 'resources', 'checks', 'error'}
    assert result['operation'] == 'check' and result['status'] == 'succeeded'
    assert result['error'] is None
    assert [(r['operation'], r['id']) for r in result['resources']] == [
        ('infra', 'settings'), ('deps', 'manifest')]
    assert [r['id'] for r in result['checks']] == ['queue-agreement']
    actions = [(result['resources'][0]['presence'], 'presence'),
               (result['resources'][1]['presence'], 'presence'),
               (result['checks'][0]['result'], 'consistency')]
    for index, resource in enumerate(result['resources']):
        available = resource['availability']
        if index == 0 and availability:
            assert available['status'] == 'succeeded' and available['reason'] is None
            actions.append((available['result'], 'availability'))
        else:
            assert available == dict(status='not_configured', result=None, reason=None)
    for action, mode in actions:
        assert action['status'] == 'succeeded' and action['error'] is None
        assert len(action['commands']) == 1
        command = action['commands'][0]
        assert command['exit_code'] == 0 and command['error'] is None
        assert command['interpretation'] == dict(success=True, value=0, error=None)
        stdout, stderr = command['stdout'], command['stderr']
        if encoded:
            assert stdout['encoding'] == stderr['encoding'] == 'base64'
            stdout = base64.b64decode(stdout['data'], validate=True)
            stderr = base64.b64decode(stderr['data'], validate=True)
        assert stderr == b'' and stdout.endswith(b'\n') and len(stdout.splitlines()) == 1
        expected = dict(status='succeeded', check=mode)
        if mode == 'consistency':
            expected.update(writer='producer', reader='consumer', variable='QUEUE_NAME', value='reports.jobs')
        assert json.loads(stdout) == expected


def run_cli(workspace):
    return subprocess.run([sys.executable, '-B', '-m', 'environment_maintenance', 'check',
        '--config', str(workspace / 'app.example.json'),
        '--parameters', str(workspace / 'parameters.example.json'), '--base-dir', str(workspace)],
        cwd=workspace, env=dict(os.environ, PYTHONPATH=os.pathsep.join((
            str(ROOT / 'src'), str(ROOT / 'examples/resource-preparation')))), capture_output=True)


def main():
    originals = {path: path.read_bytes() for path in SAMPLES.glob('*.example.json')}
    for mode in ('api', 'cli', 'optional', 'empty'):
        with TemporaryDirectory(prefix='checking-' + mode + '-') as temporary:
            workspace = Path(temporary)
            config, parameters, registry = prepare_demo(workspace)
            if mode == 'optional':
                update_requirement(config, 'infra', 'settings',
                    [dict(op='remove', path='/checks/availability')])
            if mode == 'empty':
                for operation in ('infra', 'deps', 'check'):
                    clear_requirements(config, operation)
            before = snapshot(workspace)
            if mode == 'cli':
                process = run_cli(workspace)
                assert process.returncode == 0 and process.stderr == b''
                assert process.stdout.endswith(b'\n') and len(process.stdout.splitlines()) == 1
                result = json.loads(process.stdout)
            else:
                result = check_resources(config, parameters, base_dir=workspace, interpreters=registry)
            if mode == 'empty':
                assert result == dict(operation='check', status='succeeded', resources=[], checks=[], error=None)
            else:
                assert_result(result, encoded=mode == 'cli', availability=mode != 'optional')
            assert snapshot(workspace) == before
            print(mode + ': confirmed checks; input files preserved')
    for mode in ('presence', 'availability', 'consistency'):
        with TemporaryDirectory(prefix='checking-tool-') as temporary:
            workspace = Path(temporary)
            _, values, _ = prepare_demo(workspace)
            before = snapshot(workspace)
            arguments = ['--path', values['infra_file']]
            if mode == 'consistency':
                arguments = ['--config', values['settings_config'], '--operation', values['operation'],
                    '--writer', values['writer'], '--reader', values['reader'],
                    '--queue-variable', values['variable']]
            process = subprocess.run([sys.executable, '-B', str(TOOL), mode, *arguments],
                cwd=workspace, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), capture_output=True)
            assert process.returncode == 0 and process.stderr == b''
            assert process.stdout.endswith(b'\n') and len(process.stdout.splitlines()) == 1
            expected = dict(status='succeeded', check=mode)
            if mode == 'consistency':
                expected.update(writer='producer', reader='consumer', variable='QUEUE_NAME', value='reports.jobs')
            assert json.loads(process.stdout) == expected
            assert snapshot(workspace) == before
            print('tool ' + mode + ': actual condition confirmed; input files preserved')
    for path, raw in originals.items():
        assert path.read_bytes() == raw


if __name__ == '__main__':
    main()
