"""Selection rules for operation configurations and complete requirements."""

from copy import deepcopy
from typing import Any


def configuration_for_operation(document: dict[str, Any], operation: str) -> str:
    operations = document.get("operations")
    if not isinstance(operations, dict):
        raise ValueError("operations must be an object")
    if operation not in operations:
        raise ValueError(f"Unknown operation: {operation}")
    selected = operations[operation]
    if not isinstance(selected, str) or not selected:
        raise ValueError(f"operations[{operation}]: expected a configuration path")
    return selected


class Requirements:
    """Own unique identifiers, source order and detached object selections."""

    def __init__(self, document: dict[str, Any]):
        items = document.get("requirements")
        if not isinstance(items, list):
            raise ValueError("requirements must be an array")
        self._by_id: dict[str, dict[str, Any]] = {}
        for position, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"requirements[{position}] must be an object")
            identifier = item.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError(f"requirements[{position}]: expected a nonempty id")
            if identifier in self._by_id:
                raise ValueError(f"Duplicate requirement id: {identifier}")
            self._by_id[identifier] = item

    def identifiers(self) -> list[str]:
        return list(self._by_id)

    def select(self, selection: list[str] | str) -> list[dict[str, Any]]:
        if selection == "all":
            return deepcopy(list(self._by_id.values()))
        if not isinstance(selection, list):
            raise ValueError('selection must be an array of identifiers or "all"')
        result = []
        for identifier in selection:
            if not isinstance(identifier, str) or identifier not in self._by_id:
                raise ValueError(f"Unknown requirement id: {identifier}")
            result.append(deepcopy(self._by_id[identifier]))
        return result
