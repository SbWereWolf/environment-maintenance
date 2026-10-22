"""Publish one complete selected JSON document through a local temporary file."""

import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any


def write_json(path: Path, document: dict[str, Any]) -> None:
    temporary = None
    try:
        payload = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
        mode = stat.S_IMODE(path.stat().st_mode)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload + "\n")
        temporary.chmod(mode)
        os.replace(temporary, path)
        temporary = None
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(f"Cannot write {path}: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
