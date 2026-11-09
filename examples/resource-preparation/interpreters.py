"""Application-owned extension of the standard exit-code interpreter."""
from environment_maintenance.actions.interpreters import ExitCodeInterpreter as ExitResult
from environment_maintenance.actions.interpreters import exit_result


class OpaqueResult(ExitResult):
    def interpret(self, result, options):
        answer = super().interpret(result, options)
        answer["value"] = result["stdout"]
        return answer
