"""Send one requested group termination, without waiting or escalation."""
import os
import signal


def terminate_group(pgid):
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    return True
