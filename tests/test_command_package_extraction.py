"""New independent-supply and original-consumer-use contracts on a valid baseline."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest
import environment_maintenance as original
from environment_maintenance.actions.interpreters import exit_result

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / 'fixtures' / 'command-package'


def run(argv, cwd):
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True)
    assert result.returncode == 0, (argv, result.returncode, result.stdout, result.stderr)
    return result


@pytest.fixture
def baseline_control(tmp_path):
    # This must succeed before any missing new capability can be classified RED.
    assert Path(original.__file__).is_relative_to(ROOT / "src")
    command = json.loads((FIXTURES / 'action.json').read_text())['commands'][0]
    command['argv'] = [sys.executable, '-B', str(FIXTURES / 'child.py')]
    command['cwd'] = str(tmp_path)
    result = original.execute_action({'commands': [command]}, {}, base_dir=tmp_path,
                                     interpreters={'exit': exit_result})
    row = result['commands'][0]
    assert result['status'] == 'succeeded'
    assert row['exit_code'] == 7
    assert row['stdout'] == b'package-out\x00\xff'
    assert row['stderr'] == b'package-err\xfe'
    return tmp_path


def install_project(project, temporary):
    wheel_dir = temporary / 'wheels'
    wheel_dir.mkdir(exist_ok=True)
    import shutil
    build_source = temporary / 'source-copy'
    shutil.copytree(project, build_source, ignore=shutil.ignore_patterns(
        '.git', '.venv', '__pycache__', 'build', 'dist', 'worktrees',
        '.runtime', '.pytest_cache', '*.egg-info'))
    run([sys.executable, '-I', '-B', '-m', 'build' , '--wheel', '--no-isolation',
         '--outdir', str(wheel_dir), str(build_source)], cwd=temporary)
    wheels = list(wheel_dir.glob('*.whl'))
    assert len(wheels) == 1
    target = temporary / 'installed'
    run([sys.executable, '-I', '-B', '-m', 'pip', 'install', '--no-deps',
         '--no-index', '--target', str(target), str(wheels[0])], cwd=temporary)
    return target


def library_project():
    project = ROOT / 'packages' / 'command-execution'
    assert (project / 'pyproject.toml').is_file(), (
        'NEW-INDEPENDENT-PACKAGE: valid baseline has no independently '
        'selectable command-execution package supply')
    document = tomllib.loads((project / 'pyproject.toml').read_text())
    assert document['project']['name'] == 'command-execution'
    assert document['project']['version'] == '0.1.0'
    return project


def test_independent_package_public_contract(baseline_control):
    temporary = baseline_control
    target = install_project(library_project(), temporary)
    result = run([sys.executable, '-I', '-B', str(FIXTURES / 'check_installed.py'),
                  'independent', str(target), str(FIXTURES / 'child.py'), str(temporary)],
                 cwd=temporary)
    assert result.stdout == b'independent-package-contract-ok\n'


def test_original_consumer_selects_and_uses_package(baseline_control):
    temporary = baseline_control
    document = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert 'command-execution==0.1.0' in document['project']['dependencies'], (
        'NEW-ORIGINAL-CONSUMER-USE: valid original operation still has no '
        'selected independent command package dependency')
    target = install_project(library_project(), temporary)
    # A separate output directory prevents confusing library and consumer wheels.
    consumer_build = temporary / 'consumer-build'
    consumer_build.mkdir()
    consumer_install = install_project(ROOT, consumer_build)
    # Both distributions share one test-owned import target; no product/live runtime writes.
    import shutil
    shutil.copytree(consumer_install, target, dirs_exist_ok=True)
    result = run([sys.executable, '-I', '-B', str(FIXTURES / 'check_installed.py'),
                  'consumer', str(target), str(FIXTURES / 'child.py'), str(temporary)],
                 cwd=temporary)
    assert result.stdout == b'original-consumer-use-ok\n'


def test_original_baseline_control_is_working(baseline_control):
    assert baseline_control.is_dir()
