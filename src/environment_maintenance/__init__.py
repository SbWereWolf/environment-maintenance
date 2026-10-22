"""Independent environment requirement runner. No application-specific dependencies."""
__version__ = "1.0.0"

from .actions import execute_action, plan_action

from .configuration import (
    add_requirement,
    clear_requirements,
    delete_requirement,
    list_requirement_ids,
    read_requirements,
    update_requirement,
)
