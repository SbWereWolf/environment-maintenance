"""External command adapter preserving complete byte streams and actual codes."""

from copy import deepcopy
import subprocess
from typing import Any


def run_command(invocation: dict[str, Any]) -> dict[str, Any]:
    result = subprocess.run(
        invocation["argv"], cwd=invocation["cwd"], env=invocation["env"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        shell=False, check=False,
    )
    return dict(invocation=deepcopy(invocation), exit_code=result.returncode,
                stdout=result.stdout, stderr=result.stderr)
