"""Optional generic interpretations of declared command exit codes."""


class ExitCodeInterpreter:
    def interpret(self, result, options):
        success = result["exit_code"] in options["accept"]
        return dict(success=success, value=result["exit_code"],
                    error=None if success else "command exit code is not accepted")


exit_result = ExitCodeInterpreter()
