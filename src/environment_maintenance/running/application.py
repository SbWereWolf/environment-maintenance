"""Use cases own irreversible effects and truthful per-application outcomes."""
import re

from ..actions.application import validate_execution_inputs
from ..application_resources import resolve_resources
from .domain import submitted_pgid


class RunApplications:
    def __init__(self, registry, planner, executor):
        self.registry, self.planner, self.executor = registry, planner, executor

    def run(self, rows, parameters, base_dir, interpreters, title, app, result):
        result['planned'] = len(rows)
        validate_execution_inputs(parameters, base_dir, interpreters)
        prepared = []
        for row in rows:
            try:
                resources = resolve_resources(row, parameters)
                self.planner(row, parameters, base_dir=base_dir, interpreters=interpreters)
                prepared.append((row, resources))
            except ValueError as exc:
                references = re.findall(r'\$\{[^}]*\}', repr(row))
                raise ValueError(f"run application {row['id']}: {exc}; declared placeholders {references}") from exc
        try:
            path = self.registry.reserve(title, app)
        except (OSError, ValueError) as exc:
            result['errors'].append({'environment': title, 'file': result['file'], 'error': str(exc)})
            return
        result['file'] = str(path)
        for row, resources in prepared:
            action = self.executor(row, parameters, base_dir=base_dir, interpreters=interpreters)
            pgid = submitted_pgid(action, len(row['commands']))
            result['applications'].append({'id': row['id'], 'pgid': pgid, 'result': action})
            causes = []
            if action['status'] == 'failed':
                causes.append(action['error'])
            if pgid is not None:
                result['received_pgids'] += 1
                try:
                    self.registry.put_application(path, row['id'], pgid, resources)
                except (OSError, ValueError) as exc:
                    causes.append(f'Cannot save {path}: {exc}')
            elif not causes:
                causes.append('Last command must return submitted with a positive integer pgid')
            if causes:
                result['errors'].append({'id': row['id'], 'error': '; '.join(causes)})
        try:
            self.registry.finalize_empty(path)
        except (OSError, ValueError) as exc:
            result['errors'].append({'file': str(path), 'error': str(exc)})

    def list_available(self, rows, title, parameters):
        result = {'operation': 'run-list', 'status': 'succeeded', 'environment': title,
                  'applications': {}, 'errors': []}
        if title is not None:
            records, errors = self.registry.scan()
            found = next((record for _, record in records if record.title == title), None)
            result.update(found=found is not None, errors=errors)
            rows = [row for row in rows if row['id'] not in found.applications] if found else []
            if errors:
                result['status'] = 'failed'
        for row in rows:
            result['applications'][row['id']] = {'pgid': None, **resolve_resources(row, parameters)}
        return result


class StopApplications:
    def __init__(self, registry, terminate_group):
        self.registry, self.terminate_group = registry, terminate_group

    def list_environments(self, title):
        records, errors = self.registry.scan()
        return {'operation': 'stop-list', 'status': 'failed' if errors else 'succeeded',
                'environments': [{'environment': record.title, 'file': str(path),
                    'applications': record.to_document()['applications']} for path, record in records
                    if title is None or record.title == title], 'errors': errors}

    def stop(self, title, app):
        records, errors = self.registry.scan()
        stopped = []
        for path, record in records:
            if title is not None and record.title != title:
                continue
            for name, application in record.applications.items():
                if app is not None and name != app:
                    continue
                pgid = application['pgid']
                target = {'environment': record.title, 'id': name, 'pgid': pgid}
                try:
                    if self.terminate_group(pgid):
                        stopped.append(target)
                    self.registry.remove_application(path, name)
                except (OSError, ValueError) as exc:
                    errors.append(dict(target, file=str(path), error=str(exc)))
            try:
                self.registry.finalize_empty(path)
            except (OSError, ValueError) as exc:
                errors.append({'environment': record.title, 'file': str(path), 'error': str(exc)})
        return {'operation': 'stop', 'status': 'failed' if errors else 'succeeded',
                'stopped': stopped, 'errors': errors,
                'message': '' if stopped else 'Ничего не остановлено.'}
