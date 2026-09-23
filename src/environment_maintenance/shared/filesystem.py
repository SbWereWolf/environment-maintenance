"""Shared conservative file access. Caller guarantees exclusive maintenance ownership."""
import os
from pathlib import Path
import stat
import tempfile
from .protocol import RepairError


def lexical_path(value):
    path=Path(os.path.abspath(value))
    for ancestor in reversed([path,*path.parents]):
        try:s=ancestor.lstat()
        except FileNotFoundError:continue
        if stat.S_ISLNK(s.st_mode):raise RepairError('symlink','Refusing symbolic-link path: '+str(ancestor))
    return path


def regular_or_missing(path):
    try:s=path.lstat()
    except FileNotFoundError:return False
    if not stat.S_ISREG(s.st_mode):raise RepairError('wrong_type','Expected a regular file: '+str(path))
    return True


def create_only(path,content,mode=0o600):
    """Publish complete bytes without overwriting a file created by a competing writer."""
    lexical_path(path)
    fd,temporary=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            os.fchmod(stream.fileno(),mode);stream.write(content);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,path)
    finally:os.unlink(temporary)
