"""GREEN-01: failed initial reservation never becomes a broken shared record."""
import json
import sys

import pytest

from run_stop_support import FIXTURES, application, fixture, write
from test_run_stop import lab


@pytest.mark.parametrize('limit', [0, 1])
def test_failed_initial_write_removes_only_owned_reservation_and_allows_next_run(lab, limit):
    lab.seed('retained', {'earlier': 87654321})
    retained = lab.state_path('retained').read_bytes()
    lab.run_rows([application('A')])
    failed = lab.call('-B', FIXTURES / 'reservation_fault.py', 'write', 'failed', limit,
                      entry=sys.executable)
    assert failed.returncode == 1, failed.stderr
    answer = json.loads(failed.stdout)
    assert answer['status'] == 'failed' and answer['received_pgids'] == 0
    assert answer['planned'] == 1 and answer['applications'] == []
    assert 'Errno 27' in str(answer['errors'])
    assert lab.labels() == []
    assert lab.state_path('retained').read_bytes() == retained
    assert answer['file'] == str(lab.state_path('failed'))
    assert answer['file_exists'] is False
    assert not lab.state_path('failed').exists()
    following = lab.answer('run', '--env', 'different')
    assert following['status'] == 'succeeded' and following['received_pgids'] == 1
    assert lab.labels() == ['A']
    assert lab.state('different')['applications'] == {'A': {'pgid': lab.started('A')['pgid']}}
    assert lab.state_path('retained').read_bytes() == retained


def test_failed_reservation_reports_original_write_and_cleanup_errors(lab):
    lab.run_rows([])
    failed = lab.call('-B', FIXTURES / 'reservation_fault.py', 'cleanup', 'failed', 1,
                      entry=sys.executable)
    assert failed.returncode == 1, failed.stderr
    answer = json.loads(failed.stdout)
    assert answer['status'] == 'failed' and answer['received_pgids'] == 0
    assert answer['file_exists'] is True
    assert lab.state_path('failed').read_bytes() == b'{'
    assert lab.labels() == []
    assert 'Errno 27' in str(answer['errors'])
    assert 'cleanup denied for owned reservation' in str(answer['errors'])


def test_exclusive_open_failure_preserves_file_created_by_another_owner(lab):
    lab.run_rows([])
    foreign = lab.root / 'foreign-record.json'
    record = fixture('state.json')
    record['environment-title'] = 'collision'
    write(foreign, record)
    failed = lab.call('-B', FIXTURES / 'reservation_fault.py', 'collision', 'collision', foreign,
                      entry=sys.executable)
    assert failed.returncode == 1, failed.stderr
    answer = json.loads(failed.stdout)
    assert answer['status'] == 'failed' and answer['file_exists'] is True
    assert 'exclusive-open collision fixture' in str(answer['errors'])
    assert lab.state_path('collision').read_bytes() == foreign.read_bytes()
    assert lab.labels() == []
