"""Fault only one owned OS group, before importing the genuine public CLI."""
import errno
import os
import sys

denied = int(sys.argv[1])
original = os.killpg


def killpg(group, number):
    if group == denied and number:
        raise PermissionError(errno.EPERM, "fixture denied owned group")
    return original(group, number)


os.killpg = killpg
from environment_maintenance.cli import main
raise SystemExit(main(sys.argv[2:]))
