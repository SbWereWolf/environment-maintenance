"""Учебные сменные обработчики, предоставленные обслуживаемым приложением."""


class ExitResult:
    def interpret(self, result, options):
        success = result["exit_code"] in options["accept"]
        return dict(success=success, value=result["exit_code"],
                    error=None if success else "resource is not ready")


class OpaqueResult(ExitResult):
    def interpret(self, result, options):
        answer = super().interpret(result, options)
        answer["value"] = result["stdout"]
        return answer


# Конфиг ссылается на готовый объект, а не на класс или фабрику.
exit_result = ExitResult()
