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
    """Own full-document preservation, unique identifiers and ordered changes."""

    def __init__(self, document: dict[str, Any]):
        self._document = deepcopy(document)
        items = self._document.get("requirements")
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

    def document(self) -> dict[str, Any]:
        return deepcopy(self._document)

    def _with_items(self, items: list[dict[str, Any]]) -> "Requirements":
        document = self.document()
        document["requirements"] = items
        return Requirements(document)

    def with_added(self, requirement: dict[str, Any]) -> "Requirements":
        return self._with_items([*self.select("all"), requirement])

    def with_replaced(
        self, identifier: str, requirement: dict[str, Any]
    ) -> "Requirements":
        self.select([identifier])
        return self._with_items([
            requirement if item["id"] == identifier else item
            for item in self.select("all")
        ])

    def without(self, identifier: str) -> "Requirements":
        self.select([identifier])
        return self._with_items([
            item for item in self.select("all") if item["id"] != identifier
        ])

    def cleared(self) -> "Requirements":
        return self._with_items([])
