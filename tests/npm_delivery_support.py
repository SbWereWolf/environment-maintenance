"""Transparent external package observations; does not import product code."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/npm-delivery'


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def living_group(group):
    """Observe only the group created by this helper; zombies are not running."""
    result = []
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_bytes().rpartition(b')')[2].split()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if len(fields) > 2 and int(fields[2]) == group and fields[0] not in (b'Z', b'X'):
            result.append(int(path.parent.name))
    return sorted(result)


def stop_group(group):
    before = living_group(group)
    for requested in (signal.SIGTERM, signal.SIGKILL):
        if not living_group(group):
            break
        try:
            os.killpg(group, requested)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and living_group(group):
            time.sleep(.02)
    return dict(group=group, before=before, after=living_group(group))


class PackageLab:
    def __init__(self):
        base = Path(os.environ['ENV2_PACKAGE_TEST_ROOT']).absolute()
        assert not base.is_relative_to(ROOT), 'Consumer resources must be outside source checkout'
        base.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='npm-delivery-', dir=base))
        self.logs = self.root / 'captures'
        self.logs.mkdir()
        self.index = 0
        self.children = []
        self.host_python = os.environ['ENVIRONMENT_MAINTENANCE_PYTHON']
        self.env = dict(os.environ, RELEASE_PYTHON=self.host_python)
        for key in ('PYTHONPATH', 'PYTHONHOME'):
            self.env.pop(key, None)
        self.env.update(PIP_NO_INDEX='1',
            PIP_CACHE_DIR=str(self.root / 'pip-cache'), PIP_DISABLE_PIP_VERSION_CHECK='1',
            npm_config_cache=str(self.root / 'npm-cache'), TMPDIR=str(self.root / 'tmp'))
        Path(self.env['TMPDIR']).mkdir()
        self.tools = self.root / 'observers'
        self.tools.mkdir()
        for name in ('crud.py',):
            shutil.copyfile(FIXTURES / name, self.tools / name)
        self.archive_dir = self.root / 'archive'
        self.archive_dir.mkdir()
        self.packed = self.capture('pack', ['bash', 'scripts/build-release.sh', 'npm', self.archive_dir], ROOT)
        self.available = self.packed.returncode == 0
        self.archive = None
        self.metadata = None
        if self.available:
            info = json.loads(self.packed.stdout)
            assert len(info) == 1
            self.archive = self.archive_dir / info[0]['filename']
            assert self.archive.is_file()
            self.archive_digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
            self.metadata = info[0]

    def capture(self, label, argv, cwd, *, env=None, input_bytes=None, timeout=120):
        self.index += 1
        stem = self.logs / (str(self.index).zfill(3) + '-' + label)
        selected = dict(self.env if env is None else env)
        process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=selected,
            stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.children.append(process)
        timed_out = False
        try:
            stdout, stderr = process.communicate(input_bytes, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
        remaining = living_group(process.pid)
        cleanup = stop_group(process.pid)
        stem.with_suffix('.stdout').write_bytes(stdout)
        stem.with_suffix('.stderr').write_bytes(stderr)
        observed = {key: selected[key] for key in (
            'PYTHONPATH', 'ENVIRONMENT_MAINTENANCE_PYTHON', 'PIP_NO_INDEX', 'PIP_FIND_LINKS',
            'PIP_CACHE_DIR', 'npm_config_cache', 'NPM_TEST_STDIN', 'NPM_TEST_LARGE_STDERR',
            'NPM_TEST_ENTRY_IDENTITY', 'NPM_TEST_PIP_MARKER') if key in selected}
        write_json(stem.with_suffix('.json'), dict(argv=list(map(str, argv)), cwd=str(cwd),
            environment=observed, exit_code=process.returncode, timed_out=timed_out,
            stdout_sha256=hashlib.sha256(stdout).hexdigest(), stderr_sha256=hashlib.sha256(stderr).hexdigest(),
            stdout_bytes=len(stdout), stderr_bytes=len(stderr), child_reaped=process.poll() is not None,
            group=process.pid, remaining_after_parent=remaining, group_cleanup=cleanup))
        assert not timed_out, 'Test environment process timed out; inspect full capture'
        assert not cleanup['after'], 'Owned process group cleanup incomplete'
        assert not remaining, 'Command left running descendants; group stopped, inspect full capture'
        return SimpleNamespace(returncode=process.returncode, stdout=stdout, stderr=stderr)

    def require_package(self):
        assert self.available, 'Missing working npm delivery package; inspect saved pack streams'

    def install(self, label, *, changes=None, remove=(), archive=None):
        prefix = self.root / (label + ' independent prefix Ω')
        prefix.mkdir(exist_ok=True)
        consumer = SimpleNamespace(prefix=prefix, entry=prefix / 'bin/start-app', result=None, python=None)
        if not self.available:
            return consumer
        environment = dict(self.env, **(changes or {}))
        for key in remove:
            environment.pop(key, None)
        consumer.result = self.capture('install-' + label,
            ['npm', 'install', '--global', '--prefix', prefix, '--ignore-scripts=false',
             '--no-audit', '--no-fund', archive or self.archive], self.root, env=environment)
        return consumer

    def require_consumer(self, consumer):
        self.require_package()
        assert consumer.result.returncode == 0, 'Actual npm install failed; inspect full capture'
        assert consumer.entry.is_file(), 'Installed package must provide start-app'
        if consumer.python is None:
            environments = list(consumer.prefix.rglob('pyvenv.cfg'))
            assert len(environments) == 1, 'One own runtime must belong to installed instance'
            consumer.python = environments[0].parent / 'bin/python'
            assert consumer.python.is_file()

    def scenario(self, directory, consumer):
        self.require_consumer(consumer)
        directory.mkdir(parents=True)
        serviced = directory / 'serviced cwd Ω'
        serviced.mkdir()
        plugins = directory / 'external plugins'
        plugins.mkdir()
        for source, target in (('plugins.py', 'npm_consumer_plugins.py'),
                               ('stream-profile.json', 'stream-profile.json')):
            shutil.copyfile(FIXTURES / source, plugins / target)
        for name in ('probe.py', 'stream-profile.json'):
            shutil.copyfile(FIXTURES / name, directory / name)
        main = directory / 'main.json'
        shutil.copyfile(FIXTURES / 'main.json', main)
        documents = {}
        for operation in ('infra', 'deps', 'adjust', 'check', 'run'):
            command = fixture('command.json')
            command['argv'][4] = operation
            requirement = dict(id='selected', commands=[command])
            if operation in ('infra', 'deps'):
                requirement['checks'] = dict(presence=dict(commands=[command]))
            document = dict(requirements=[requirement], owner=dict(unchanged=[False, 0, None]))
            path = directory / (operation + '.json')
            write_json(path, document)
            documents[operation] = path
        events = directory / 'events.jsonl'
        parameters = dict(python=str(consumer.python), probe=str(directory / 'probe.py'),
            events=str(events), serviced=str(serviced), token='chosen-token-Ω')
        values = directory / 'values Ω with spaces.json'
        write_json(values, parameters)
        return SimpleNamespace(directory=directory, serviced=serviced, plugins=plugins,
            main=main, documents=documents, events=events, values=values, parameters=parameters)

    def invoke(self, consumer, scenario, operation='infra', *, input_bytes=None, changes=None):
        self.require_consumer(consumer)
        argv = [consumer.entry, operation, '--config', scenario.main, '--parameters', scenario.values,
                '--base-dir', scenario.serviced]
        if operation != 'check':
            argv += ['--requirements', '["selected"]']
        environment = dict(self.env, PYTHONPATH=str(scenario.plugins), **(changes or {}))
        return self.capture(operation, argv, scenario.serviced, env=environment, input_bytes=input_bytes)

    def close(self):
        groups = [stop_group(process.pid) for process in self.children]
        for process in self.children:
            process.wait(timeout=5)
        closed = all(not living_group(process.pid) for process in self.children)
        if self.archive is not None:
            assert hashlib.sha256(self.archive.read_bytes()).hexdigest() == self.archive_digest
        write_json(self.root / 'resource-closure.json', dict(no_live_owned_children=closed,
            owned_groups=groups,
            archive_digest=getattr(self, 'archive_digest', None), archive_unchanged=True,
            temporary_material_retained_until_task_delivery=True))
        assert closed, 'Owned descendants remain alive; closure receipt is not successful'
