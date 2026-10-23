"""Check independent conditions while retaining every actually attempted result."""
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..actions.application import ResultInterpreter, validate_execution_inputs
from .domain import declared_resource_checks


def _plan_with_context(action, context, parameters, *, base_dir, interpreters, planner):
    try:
        planner(action, parameters, base_dir=base_dir, interpreters=interpreters)
    except ValueError as exc:
        raise ValueError(f"{context}: {exc}") from exc


def _prepare_resources(documents, parameters, *, base_dir, interpreters, planner):
    resources = []
    for operation in ('infra', 'deps'):
        for requirement in documents[operation]:
            context = f"{operation} requirement {requirement['id']}"
            try:
                presence, availability = declared_resource_checks(requirement)
            except ValueError as exc:
                raise ValueError(f"{context}: {exc}") from exc
            for kind, action in (('presence', presence), ('availability', availability)):
                if action is not None:
                    _plan_with_context(action, f"{context} {kind}", parameters,
                        base_dir=base_dir, interpreters=interpreters, planner=planner)
            resources.append((operation, requirement['id'], presence, availability))
    for requirement in documents['check']:
        _plan_with_context(requirement, f"check requirement {requirement['id']}", parameters,
            base_dir=base_dir, interpreters=interpreters, planner=planner)
    return resources


def _check_resource(operation, identifier, presence, availability, parameters, *,
                    base_dir, interpreters, executor):
    result = executor(presence, parameters, base_dir=base_dir, interpreters=interpreters)
    if availability is None:
        available = dict(status='not_configured', result=None, reason=None)
    elif result['status'] == 'failed':
        available = dict(status='not_attempted', result=None, reason='presence_failed')
    else:
        attempted = executor(availability, parameters, base_dir=base_dir, interpreters=interpreters)
        available = dict(status=attempted['status'], result=attempted, reason=None)
    return dict(operation=operation, id=identifier, presence=result, availability=available)


def _resource_error(resource):
    if resource['presence']['status'] == 'failed':
        kind, result = 'presence', resource['presence']
    elif resource['availability']['status'] == 'failed':
        kind, result = 'availability', resource['availability']['result']
    else:
        return None
    return f"{resource['operation']} requirement {resource['id']} {kind}: {result['error']}"


def check_resources(
    config_path: str | Path,
    parameters: dict[str, Any],
    *,
    base_dir: str | Path,
    interpreters: dict[str, ResultInterpreter],
    reader: Callable,
    planner: Callable,
    executor: Callable,
) -> dict[str, Any]:
    validate_execution_inputs(parameters, base_dir, interpreters)
    documents = {}
    for operation in ('infra', 'deps', 'check'):
        try:
            documents[operation] = reader(config_path, operation, 'all')
        except ValueError as exc:
            raise ValueError(f"{operation} configuration: {exc}") from exc
    prepared = _prepare_resources(documents, parameters, base_dir=base_dir,
                                  interpreters=interpreters, planner=planner)
    resources, checks = [], []
    error = None
    for operation, identifier, presence, availability in prepared:
        resource = _check_resource(operation, identifier, presence, availability, parameters,
            base_dir=base_dir, interpreters=interpreters, executor=executor)
        resources.append(resource)
        error = error or _resource_error(resource)
    for requirement in documents['check']:
        result = executor(requirement, parameters, base_dir=base_dir, interpreters=interpreters)
        checks.append(dict(id=requirement['id'], result=result))
        if result['status'] == 'failed' and error is None:
            error = f"check requirement {requirement['id']}: {result['error']}"
    return dict(operation='check', status='succeeded' if error is None else 'failed',
                resources=resources, checks=checks, error=error)
