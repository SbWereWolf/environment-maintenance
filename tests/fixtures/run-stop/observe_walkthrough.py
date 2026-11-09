"""Observe the existing public API without changing its returned values/errors."""
import json
from pathlib import Path
import runpy
import sys

example, record = map(Path, sys.argv[1:])
sys.path.insert(0, str(example.parent))
import environment_maintenance as api
original = api.prepare_resources


def observed(config, operation, selection, *args, **kwargs):
    row = {"operation": operation, "selection": selection}
    try:
        value = original(config, operation, selection, *args, **kwargs)
    except Exception:
        row["outcome"] = "refused"
        raise
    else:
        row["outcome"] = "returned"
        return value
    finally:
        with record.open("a") as stream:
            stream.write(json.dumps(row) + "\n")


api.prepare_resources = observed
runpy.run_path(str(example), run_name="__main__")
