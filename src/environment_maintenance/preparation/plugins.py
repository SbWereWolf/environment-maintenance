"""Compose configured result interpreters for the ordinary JSON CLI transport."""
import importlib
import json
from typing import Any

from ..actions.application import ResultInterpreter


def _require_json_data(value: Any) -> None:
    if value is None or type(value) in (str, bool, int, float):
        return
    if type(value) is list:
        for item in value:
            _require_json_data(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("JSON objects require string keys")
            _require_json_data(item)
        return
    raise ValueError(f"Unsupported JSON value type: {type(value).__name__}")


class JsonResultInterpreter:
    def __init__(self, interpreter: ResultInterpreter):
        self._interpreter = interpreter

    def interpret(self, raw: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
        answer = self._interpreter.interpret(raw, options)
        # JSON encoding alone silently coerces tuple values and non-string keys.
        _require_json_data(answer)
        json.dumps(answer, allow_nan=False)
        return answer


def load_interpreters(document: dict[str, Any]) -> dict[str, ResultInterpreter]:
    declarations = document.get('interpreters')
    if not isinstance(declarations, dict):
        raise ValueError("interpreters must be an object")
    result = {}
    for name, declaration in declarations.items():
        if not isinstance(name, str) or not name:
            raise ValueError("interpreters require nonempty names")
        if not isinstance(declaration, dict):
            raise ValueError(f"interpreter {name}: expected module/attribute object")
        module, attribute = declaration.get('module'), declaration.get('attribute')
        if not isinstance(module, str) or not module or not isinstance(attribute, str) or not attribute:
            raise ValueError(f"interpreter {name}: module and attribute must be nonempty strings")
        try:
            interpreter = getattr(importlib.import_module(module), attribute)
        except Exception as exc:
            raise ValueError(f"interpreter {name} {module}:{attribute}: {exc}") from exc
        if not callable(getattr(interpreter, 'interpret', None)):
            raise ValueError(f"interpreter {name} {module}:{attribute}: callable interpret is required")
        result[name] = JsonResultInterpreter(interpreter)
    return result
