"""Test-owned interpretation makes the forbidden legacy command otherwise valid."""


class ExitResult:
    def interpret(self, raw, options):
        success = raw['exit_code'] in options['accept']
        return dict(success=success, value=raw['exit_code'],
                    error=None if success else 'external fixture command failed')


exit_result = ExitResult()
