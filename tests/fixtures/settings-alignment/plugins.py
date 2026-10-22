"""Test-owned result interpretation independent of the alignment implementation."""


class ExitResult:
    def interpret(self, raw, options):
        success = raw['exit_code'] in options['accept']
        return dict(success=success, value=raw['exit_code'],
                    error=None if success else 'external process failed')


exit_result = ExitResult()
