"""Read actual package identity using the installed isolated Python."""
import importlib.metadata
import json
import sys

import environment_maintenance

print(json.dumps({
    "origin": environment_maintenance.__file__,
    "prefix": sys.prefix,
    "module_version": environment_maintenance.__version__,
    "distribution_version": importlib.metadata.version("environment-maintenance"),
}))
