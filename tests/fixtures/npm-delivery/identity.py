"""Observe actual installed imports and distribution metadata externally."""
import importlib.metadata
import json
import sys
import environment_maintenance
import jsonpatch
import jsonpointer

print(json.dumps(dict(version=environment_maintenance.__version__,
    metadata=importlib.metadata.version('environment-maintenance'),
    executable=sys.executable, prefix=sys.prefix,
    modules={m.__name__: m.__file__ for m in (environment_maintenance, jsonpatch, jsonpointer)})))
