"""EM dispatch-error projection, frozen before its repair."""
from copy import deepcopy
import json
import threading
import pytest
import command_execution.execution as execution
from environment_maintenance import execute_chain


@pytest.mark.parametrize('all_threads', [False, True])
@pytest.mark.parametrize('stage', ['construct', 'start'])
@pytest.mark.parametrize('prior_success', [True, False])
def test_async_dispatch_failure_keeps_caller_result_and_successors(tmp_path, monkeypatch, stage, prior_success, all_threads):
    real = threading.Thread
    def factory(*args, **kwargs):
        if all_threads or kwargs.get('target').__name__ == 'execute':
            if stage == 'construct':
                raise RuntimeError('dispatch unavailable')
            worker = real(*args, **kwargs)
            def fail():
                raise RuntimeError('dispatch unavailable')
            worker.start = fail
            return worker
        return real(*args, **kwargs)
    monkeypatch.setattr(execution.threading, 'Thread', factory)
    rows = [dict(argv=['worker', name], cwd='.', env={},
        interpreter=dict(name='answer', options={}), mode=mode, on_error='continue')
        for name, mode in [('before', 'sync'), ('background', 'async'), ('after', 'sync')]]
    calls, notifications = [], []
    initial, advanced = {'n': [1]}, {'n': [2]}
    class Interpreter:
        def interpret(self, raw, options):
            if raw['stdout'] == b'before':
                return dict(success=prior_success, value='before-value',
                    error=None if prior_success else 'before failed', next_input=deepcopy(advanced))
            return dict(success=True, value='after-value', error=None)
    def runner(invocation):
        calls.append(deepcopy(invocation))
        return dict(exit_code=0, stdout=invocation['argv'][1].encode(), stderr=b'')
    caller = threading.get_ident()
    def callback(row):
        notifications.append((threading.get_ident(), deepcopy(row)))
        row['input_data']['n'].append('callback-only')
        row['invocation']['argv'].append('callback-only')
    result = execute_chain({'commands': rows}, {}, input_data=initial, base_dir=tmp_path,
        interpreters={'answer': Interpreter()}, run_command=runner, on_result=callback)
    assert [row['argv'][1] for row in calls] == ['before', 'after']
    assert [json.loads(row['stdin']) for row in calls] == [initial, advanced]
    assert [row[1]['index'] for row in notifications] == [0, 1, 2]
    assert all(context == caller for context, row in notifications)
    failed = result['commands'][1]
    assert failed['state'] == 'completed'
    assert failed['input_data'] == advanced
    assert failed['error'] == 'commands[1] dispatch: dispatch unavailable'
    assert failed['exception'] == dict(type='RuntimeError', message='dispatch unavailable')
    assert all(failed[key] is None for key in ['exit_code', 'stdout', 'stderr', 'interpretation'])
    assert failed['invocation']['argv'] == ['worker', 'background']
    assert notifications[1][1] == failed
    assert result['status'] == ('succeeded' if prior_success else 'failed')
    assert result['error'] == (None if prior_success else 'interpreter answer: before failed')
    assert result['data'] == advanced
    assert initial == {'n': [1]}
