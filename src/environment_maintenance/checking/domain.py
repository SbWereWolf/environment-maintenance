"""Declared conditions of a resource, independent of its installation actions."""
from typing import Any

from ..actions.domain import declared_commands


def declared_resource_checks(requirement: dict[str, Any]) -> tuple[dict, dict | None]:
    checks = requirement.get('checks')
    if not isinstance(checks, dict):
        raise ValueError("checks must be an object with presence")
    if 'presence' not in checks:
        raise ValueError("checks.presence is required")
    for kind in ('presence', 'availability'):
        if kind in checks:
            try:
                declared_commands(checks[kind])
            except ValueError as exc:
                raise ValueError(f"checks.{kind}: {exc}") from exc
    return checks['presence'], checks.get('availability')
