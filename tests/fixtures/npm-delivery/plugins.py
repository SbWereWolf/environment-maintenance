"""Explicit consumer plugin, exercising standard import, input and diagnostics."""
import json
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
        return dict(success=success, value=dict(plugin=self.label, stdin=received),
                    error=None if success else 'consumer action failed')


first = ConsumerResult('first')
second = ConsumerResult('second')
