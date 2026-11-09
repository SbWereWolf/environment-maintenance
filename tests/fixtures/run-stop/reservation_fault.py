"""Enter the real CLI with one bounded reservation I/O fault in an own process."""
import errno
from pathlib import Path
import resource
import signal
import sys
import tempfile

from environment_maintenance.cli import main

mode, title, argument = sys.argv[1:4]
target = Path(tempfile.gettempdir()) / 'environment-maintenance' / ('env-' + title + '.json')
if mode == 'collision':
    original_open = Path.open

    def open_with_collision(path, mode='r', *args, **kwargs):
        if path == target and mode == 'x':
            with original_open(path, 'wb') as stream:
                stream.write(Path(argument).read_bytes())
            raise FileExistsError(errno.EEXIST, 'exclusive-open collision fixture', str(path))
        return original_open(path, mode, *args, **kwargs)

    Path.open = open_with_collision
else:
    if mode == 'cleanup':
        original_unlink = Path.unlink

        def unlink_with_denial(path, *args, **kwargs):
            if path == target:
                raise PermissionError(errno.EACCES, 'cleanup denied for owned reservation', str(path))
            return original_unlink(path, *args, **kwargs)

        Path.unlink = unlink_with_denial
    else:
        assert mode == 'write'
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
    resource.setrlimit(resource.RLIMIT_FSIZE, (int(argument), int(argument)))

raise SystemExit(main(['run', '--env', title]))
