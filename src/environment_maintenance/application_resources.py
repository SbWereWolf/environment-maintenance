"""Resolve declared application resource data without inspecting or acquiring it."""
import json
from string import Template


def _render(value, parameters, field):
    try:
        return Template(value).substitute(parameters)
    except (KeyError, ValueError) as exc:
        raise ValueError(f'{field} template: {exc}') from exc


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonempty string')
    return value


def _port(value, parameters):
    if isinstance(value, str):
        value = _render(value, parameters, 'port')
        if not value.isdecimal():
            raise ValueError('port must be an integer from 1 to 65535')
        value = int(value)
    if type(value) is not int or not 1 <= value <= 65535:
        raise ValueError('port must be an integer from 1 to 65535')
    return value


def _metadata(value, parameters, field, required):
    if not isinstance(value, dict) or not value:
        raise ValueError(f'{field} must be a nonempty object')
    result = {}
    for key, item in value.items():
        _text(key, f'{field} key')
        if isinstance(item, str):
            item = _render(item, parameters, f'{field}.{key}')
        elif item is not None and type(item) not in (bool, int, float):
            raise ValueError(f'{field}.{key} must be a JSON scalar')
        result[key] = item
    for key in required:
        _text(result.get(key), f'{field}.{key}')
    return result


def resolve_resources(application, parameters):
    """Return a distinct resolved description; application PGID is owned by launch."""
    if 'resources' not in application:
        return {}
    try:
        declared = application['resources']
        if not isinstance(declared, dict):
            raise ValueError('resources must be an object')
        unknown = set(declared) - {'host', 'port', 'queue', 'scheduler'}
        if unknown:
            raise ValueError(f'unknown resources fields: {sorted(unknown)}')
        if ('host' in declared) != ('port' in declared):
            raise ValueError('host and port must be declared together')
        result = {}
        if 'host' in declared:
            host = _text(declared['host'], 'host')
            result['host'] = _text(_render(host, parameters, 'host'), 'host')
            result['port'] = _port(declared['port'], parameters)
        for field, required in [('queue', ('driver', 'name')),
                                ('scheduler', ('application', 'command'))]:
            if field in declared:
                result[field] = _metadata(declared[field], parameters, field, required)
        json.dumps(result, allow_nan=False)
        return result
    except ValueError as exc:
        raise ValueError(f"Application {application['id']} resources: {exc}") from exc
