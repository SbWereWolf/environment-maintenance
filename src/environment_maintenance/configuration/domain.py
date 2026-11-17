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


def validate_selection(selection: list[str] | str) -> None:
    if selection == "all":
        return
    if not isinstance(selection, list):
        raise ValueError('selection must be an array of identifiers or "all"')
    seen = set()
    for position, identifier in enumerate(selection):
        if not isinstance(identifier, str):
            raise ValueError(f"selection[{position}]: expected an identifier")
        if identifier in seen:
            raise ValueError(f"Duplicate selected id {identifier} at position {position}; remove the repeated id")
        seen.add(identifier)


from command_execution import DocumentCollection


class Requirements:
    """EM names and missing-selection projection over the shared collection."""
    def __init__(self, document, array_name='requirements'):
        self._collection = DocumentCollection(document, array_name)

    def identifiers(self):
        return self._collection.ids()

    def select_available(self, selection):
        validate_selection(selection)
        if selection == 'all':
            return self._collection.select(), []
        known = self.identifiers()
        return self._collection.select([key for key in selection if key in known]), [key for key in selection if key not in known]

    def select(self, selection):
        rows, missing = self.select_available(selection)
        if missing:
            raise ValueError(f'Unknown requirement id: {missing[0]}')
        return rows

    def document(self):
        return self._collection.document()

    def _from(self, collection):
        return type(self)(collection.document(), collection.array_name)

    def with_added(self, value):
        return self._from(self._collection.add(value))

    def with_replaced(self, identifier, value):
        return self._from(self._collection.replace(identifier, value))

    def without(self, identifier):
        return self._from(self._collection.delete(identifier))

    def cleared(self):
        return self._from(self._collection.clear())
