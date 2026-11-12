"""Observe the real public main's resolution boundary without replacing it."""
import sys

from environment_maintenance import cli

resolve = cli.resolve_invocation


def observed_resolution(*args, **kwargs):
    sys.stderr.write("INVOCATION_BOUNDARY\n")
    sys.stderr.flush()
    return resolve(*args, **kwargs)


cli.resolve_invocation = observed_resolution
raise SystemExit(cli.main(sys.argv[1:]))
