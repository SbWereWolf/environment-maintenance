import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from environment_maintenance.catalogue import Catalogue, load_catalog
from environment_maintenance.engine import execute
from environment_maintenance.process import run_action


SCHEMA = "environment-maintenance/action-result/v2"
SECRET = "SYNTHETIC_REMEDIATION_SECRET"


def action(cwd="."):
    script = (
        "import json;print(json.dumps({'schema':'environment-maintenance/action-result/v2',"
        "'requirement_id':'sample','action':'check','state':'satisfied'}))"
    )
    return {
        "argv": [sys.executable, "-S", "-c", script, SECRET],
        "cwd": str(cwd),
        "env": {"TOKEN": SECRET},
        "output": {"schema": SCHEMA},
        "max_output_bytes": 4096,
        "execution_bound_seconds": 3,
    }


def escapes_runtime_error(operation):
    try:
        operation()
    except RuntimeError:
        return True
    except Exception:
        return False
    return False


with TemporaryDirectory() as directory:
    root = Path(directory)
    selected = action()
    catalog = Catalogue(
        root,
        root / "catalog.json",
        {
            "schema": "environment-maintenance/catalog/v2",
            "parameters": {
                "secret": {"type": "string", "default": SECRET, "secret": True},
            },
            "inherit_env": [],
            "requirements": [{
                "id": "sample",
                "check": selected,
                "install": selected,
                "repair": selected,
            }],
        },
    )
    leaked = SECRET in json.dumps(execute(catalog, "check", environ={}))
    loop = root / "loop"
    os.symlink("loop", loop)
    catalog_escaped = escapes_runtime_error(lambda: load_catalog(loop))
    cwd_escaped = escapes_runtime_error(
        lambda: run_action(action(loop), "sample", "check", cwd=root, environ={})
    )

if leaked and catalog_escaped and cwd_escaped:
    print("ENV_MAINT_V2_REMEDIATION_RED")
    raise SystemExit(1)
print("ENV_MAINT_V2_REMEDIATION_RED_INVALID")
raise SystemExit(2)
