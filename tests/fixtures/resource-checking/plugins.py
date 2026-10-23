"""Test-owned interpreters do not perform resource checks or orchestration."""


class ExitResult:
    def interpret(self, result, options):
        success = result['exit_code'] in options['accept']
        return dict(success=success, value=result['exit_code'],
                    error=None if success else 'external check failed')


class OpaqueResult(ExitResult):
    def interpret(self, result, options):
        answer = super().interpret(result, options)
        answer['value'] = result['stdout']
        return answer


exit_result = ExitResult()
opaque_result = OpaqueResult()
