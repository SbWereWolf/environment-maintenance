"""Configuration use cases compose domain changes with injected external ports."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .domain import Requirements, configuration_for_operation


DocumentReader = Callable[[Path], dict[str, Any]]
DocumentWriter = Callable[[Path, dict[str, Any]], None]
RequirementPatcher = Callable[
    [dict[str, Any], list[dict[str, Any]]], dict[str, Any]
]


def read_operation_configuration(
    read_document: DocumentReader, config_path: str | Path, operation: str
) -> tuple[Path, dict[str, Any]]:
    main_path = Path(config_path)
    main_document = read_document(main_path)
    selected_path = Path(configuration_for_operation(main_document, operation))
    if not selected_path.is_absolute():
        selected_path = main_path.parent / selected_path
    return selected_path, read_document(selected_path)


class ConfigurationReader:
    def __init__(self, read_document: DocumentReader):
        self._read_document = read_document

    def _requirements(self, config_path: str | Path, operation: str) -> Requirements:
        _, document = read_operation_configuration(
            self._read_document, config_path, operation
        )
        try:
            return Requirements(document, "applications" if operation == "run" else "requirements")
        except ValueError as exc:
            raise ValueError(f"{operation} configuration {config_path}: {exc}") from exc

    def read_for_execution(self, config_path, operation, selection):
        try:
            return self._requirements(config_path, operation).select_available(selection)
        except ValueError as exc:
            raise ValueError(f"{operation} configuration {config_path}: {exc}") from exc

    def list_ids(self, config_path: str | Path, operation: str) -> list[str]:
        return self._requirements(config_path, operation).identifiers()

    def read(
        self,
        config_path: str | Path,
        operation: str,
        selection: list[str] | str,
    ) -> list[dict[str, Any]]:
        return self._requirements(config_path, operation).select(selection)


class ConfigurationWriter:
    def __init__(
        self,
        read_document: DocumentReader,
        write_document: DocumentWriter,
        apply_changes: RequirementPatcher,
    ):
        self._read_document = read_document
        self._write_document = write_document
        self._apply_changes = apply_changes

    def _edit(
        self,
        config_path: str | Path,
        operation: str,
        transformation: Callable[[Requirements], Requirements],
    ) -> None:
        path = Path(config_path)
        try:
            path, document = read_operation_configuration(
                self._read_document, config_path, operation
            )
            result = transformation(Requirements(document, "applications" if operation == "run" else "requirements"))
            self._write_document(path, result.document())
        except ValueError as exc:
            raise ValueError(f"{operation} configuration {path}: {exc}") from exc

    def add(
        self, config_path: str | Path, operation: str, requirement: dict[str, Any]
    ) -> None:
        self._edit(config_path, operation, lambda items: items.with_added(requirement))

    def _updated(
        self,
        requirements: Requirements,
        identifier: str,
        changes: list[dict[str, Any]],
    ) -> Requirements:
        original = requirements.select([identifier])[0]
        result = self._apply_changes(original, changes)
        return requirements.with_replaced(identifier, result)

    def update(
        self,
        config_path: str | Path,
        operation: str,
        identifier: str,
        changes: list[dict[str, Any]],
    ) -> None:
        self._edit(
            config_path, operation,
            lambda items: self._updated(items, identifier, changes),
        )

    def delete(
        self, config_path: str | Path, operation: str, identifier: str
    ) -> None:
        self._edit(config_path, operation, lambda items: items.without(identifier))

    def clear(self, config_path: str | Path, operation: str) -> None:
        self._edit(config_path, operation, lambda items: items.cleared())
