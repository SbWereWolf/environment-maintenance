"""Test-owned exit interpreter; never inspects application messages."""


class ExitResult:
    def interpret(self, raw, options):
        success = raw["exit_code"] in options["accept"]
        return {"success": success, "value": raw["exit_code"],
                "error": None if success else "fixture command failed"}


exit_result = ExitResult()
