"""Read use cases depend on domain rules and an injected document reader."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .domain import Requirements, configuration_for_operation


DocumentReader = Callable[[Path], dict[str, Any]]


class ConfigurationReader:
    def __init__(self, read_document: DocumentReader):
        self._read_document = read_document

    def _requirements(self, config_path: str | Path, operation: str) -> Requirements:
        main_path = Path(config_path)
        main_document = self._read_document(main_path)
        selected_path = Path(configuration_for_operation(main_document, operation))
        if not selected_path.is_absolute():
            selected_path = main_path.parent / selected_path
        return Requirements(self._read_document(selected_path))

    def list_ids(self, config_path: str | Path, operation: str) -> list[str]:
        return self._requirements(config_path, operation).identifiers()

    def read(
        self,
        config_path: str | Path,
        operation: str,
        selection: list[str] | str,
    ) -> list[dict[str, Any]]:
        return self._requirements(config_path, operation).select(selection)
