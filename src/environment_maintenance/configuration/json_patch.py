"""EM's supported JSON changes use the shared pure path editor."""
from command_execution import JSONPathEditor


def apply_changes(requirement, changes):
    return JSONPathEditor().patch(requirement, changes)
