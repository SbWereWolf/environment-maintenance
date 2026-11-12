"""Persisted environment facts, independent of files and process operations."""
from dataclasses import dataclass
from copy import deepcopy


@dataclass
class EnvironmentRecord:
    title: str
    applications: dict[str, dict]
    format_version: object = 1

    @classmethod
    def from_document(cls, document):
        title, apps = document.get('environment-title'), document.get('applications')
        if not isinstance(title, str) or not title or not isinstance(apps, dict):
            raise ValueError('Expected environment-title and applications object')
        if 'format-version' not in document:
            raise ValueError('Missing format-version')
        values = {}
        for name, row in apps.items():
            if not isinstance(name, str) or not name or not isinstance(row, dict):
                raise ValueError('Expected named application object')
            pgid = row.get('pgid')
            if type(pgid) is not int or pgid <= 0:
                raise ValueError(f'Application {name}: pgid must be a positive integer')
            values[name] = deepcopy(row)
        return cls(title, values, document['format-version'])

    def to_document(self):
        return {'format-version': self.format_version, 'environment-title': self.title,
                'applications': deepcopy(self.applications)}
