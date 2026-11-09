"""Observe the installed optional interpreter without importing application code."""
import importlib.util
import json
from pathlib import Path
import sys

import environment_maintenance

assert Path(environment_maintenance.__file__).is_relative_to(Path(sys.prefix))
name = 'environment_maintenance.actions.interpreters'
assert importlib.util.find_spec(name) is not None, 'Required packaged interpreter is absent'
from environment_maintenance.actions.interpreters import exit_result

code, accepted = int(sys.argv[1]), int(sys.argv[2])
print(json.dumps(exit_result.interpret(dict(exit_code=code), dict(accept=[accepted]))))
