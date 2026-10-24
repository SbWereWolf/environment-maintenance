"""Explicit consumer plugin, exercising standard import, input and diagnostics."""
import json
import importlib.metadata
import os
from pathlib import Path
import sys

profile = json.loads(Path(__file__).with_name('stream-profile.json').read_text())
received = sys.stdin.buffer.read().decode('utf-8') if os.environ.get('NPM_TEST_STDIN') == '1' else ''
if os.environ.get('NPM_TEST_LARGE_STDERR') == '1':
    sys.stderr.buffer.write(bytes.fromhex(profile['large_stderr_pattern_hex']) * profile['large_stderr_repetitions'])


class ConsumerResult:
    def __init__(self, label):
        self.label = label

    def interpret(self, result, options):
        success = result['exit_code'] in options['accept']
        value = dict(plugin=self.label, stdin=received)
        if os.environ.get('NPM_TEST_ENTRY_IDENTITY') == '1':
            import environment_maintenance
            import jsonpatch
            import jsonpointer
            value['identity'] = dict(pid=os.getpid(), executable=sys.executable, prefix=sys.prefix,
                version=environment_maintenance.__version__,
                metadata=importlib.metadata.version('environment-maintenance'),
                modules={m.__name__: m.__file__ for m in (environment_maintenance, jsonpatch, jsonpointer)})
        return dict(success=success, value=value,
                    error=None if success else 'consumer action failed')


first = ConsumerResult('first')
second = ConsumerResult('second')
