"""One filesystem owner; the shared lock protects new-record creation only."""
import fcntl
import json
from pathlib import Path
import tempfile
from copy import deepcopy

from ..configuration.json_file import read_json, write_json
from .domain import EnvironmentRecord


class FileRegistry:
    def __init__(self):
        self.root = Path(tempfile.gettempdir()).absolute() / 'environment-maintenance'

    def path_for(self, title):
        return self.root / ('env-' + title + '.json')

    def _read(self, path):
        try:
            return EnvironmentRecord.from_document(read_json(path))
        except ValueError as exc:
            raise ValueError(f'{path}: {exc}') from exc

    def scan(self):
        records, errors = [], []
        try:
            paths = sorted(path for path in self.root.iterdir()
                           if path.name.startswith('env-') and path.name.endswith('.json')) if self.root.exists() else []
        except OSError as exc:
            return [], [{'file': str(self.root), 'error': str(exc)}]
        for path in paths:
            try:
                records.append((path, self._read(path)))
            except (ValueError, OSError) as exc:
                errors.append({'file': str(path), 'error': str(exc)})
        return records, errors

    def _existing(self, records, title, app):
        for path, record in records:
            if record.title == title:
                if app is None and record.applications:
                    raise ValueError(f'{title}: environment is not empty; use another name or add one --app')
                if app is not None and app in record.applications:
                    raise ValueError(f'{title}: application {app} is already registered; stop it before relaunching')
                return path
        return None

    def reserve(self, title, app):
        records, errors = self.scan()
        existing = self._existing(records, title, app)
        if existing is not None:
            return existing
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / 'registry.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                records, errors = self.scan()
                existing = self._existing(records, title, app)
                if existing is not None:
                    return existing
                if errors:
                    raise ValueError('Cannot establish available environment name: ' + str(errors))
                path = self.path_for(title)
                stream = path.open('x', encoding='utf-8')
                try:
                    with stream:
                        json.dump(EnvironmentRecord(title, {}).to_document(), stream, ensure_ascii=False)
                        stream.write('\n')
                except OSError as exc:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError as cleanup:
                        raise OSError(f'{exc}; cannot remove failed reservation {path}: {cleanup}') from exc
                    raise
                return path
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def put_application(self, path, name, pgid, resources=None):
        record = self._read(path)
        record.applications[name] = {'pgid': pgid, **deepcopy(resources or {})}
        write_json(path, record.to_document())

    def remove_application(self, path, name):
        record = self._read(path)
        record.applications.pop(name, None)
        if record.applications:
            write_json(path, record.to_document())
        else:
            path.unlink()

    def finalize_empty(self, path):
        if path.exists() and not self._read(path).applications:
            path.unlink()
