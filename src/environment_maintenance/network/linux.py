"""Linux TCP reservations and declared-process listener evidence."""
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import socket
import sys

from .domain import NetworkFailure, PortRequest


@contextmanager
def reserve_port(host: str, requested_port: int):
    candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            candidate.bind((host, requested_port))
        except OSError as exc:
            if requested_port == 0 or exc.errno != errno.EADDRINUSE:
                raise
            candidate.close()
            candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            candidate.bind((host, 0))
        yield candidate.getsockname()[1]
    finally:
        candidate.close()


def _identity(pid: int):
    raw = Path(f'/proc/{pid}/stat').read_text(encoding='utf-8')
    fields = raw[raw.rindex(')') + 1:].split()
    return fields[0], fields[19]


def _matching_identity(request):
    state, ticks = _identity(request.owner.pid)
    if state in ('Z', 'X', 'x'):
        raise NetworkFailure('ownership_mismatch', request.parameter,
                             f'Process {request.owner.pid} is dead')
    if ticks != request.owner.start_ticks:
        raise NetworkFailure('ownership_mismatch', request.parameter,
                             f'Process {request.owner.pid} start_ticks mismatch')


def confirm_owner(request: PortRequest):
    pid = request.owner.pid
    try:
        _matching_identity(request)
        inodes = set()
        for descriptor in Path(f'/proc/{pid}/fd').iterdir():
            try:
                target = os.readlink(descriptor)
            except FileNotFoundError:
                # A descriptor can close while a live process is being observed.
                continue
            if target.startswith('socket:[') and target.endswith(']'):
                inodes.add(target[8:-1])
        table = Path(f'/proc/{pid}/net/tcp').read_text(encoding='ascii')
        found = False
        for row in table.splitlines()[1:]:
            fields = row.split()
            if len(fields) < 10:
                raise ValueError('Incomplete kernel TCP listener evidence')
            address, port = fields[1].split(':')
            host = socket.inet_ntoa(int(address, 16).to_bytes(4, sys.byteorder))
            if (fields[3] == '0A' and fields[9] in inodes
                    and int(port, 16) == request.current_port
                    and (host == request.host or host == '0.0.0.0')):
                found = True
        _matching_identity(request)
        if not found:
            raise NetworkFailure('ownership_mismatch', request.parameter,
                                 f'Process {pid}: matching owned listener is missing')
    except (OSError, ValueError, IndexError) as exc:
        if isinstance(exc, (FileNotFoundError, ProcessLookupError)):
            try:
                _matching_identity(request)
            except (FileNotFoundError, ProcessLookupError) as missing:
                raise NetworkFailure('ownership_mismatch', request.parameter,
                                     f'Process {pid} not found: {missing}') from missing
            except (OSError, ValueError, IndexError) as unavailable:
                raise NetworkFailure('ownership_unavailable', request.parameter,
                                     str(unavailable)) from unavailable
        raise NetworkFailure('ownership_unavailable', request.parameter, str(exc)) from exc
