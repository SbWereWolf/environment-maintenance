"""App-supplied test interpreter; no product imports or expected-value generator."""


class ExitResult:
    def interpret(self, raw, options):
        accepted = raw['exit_code'] in options['accept']
        return dict(success=accepted, value=dict(code=raw['exit_code']),
                    error=None if accepted else 'external command failed')


exit_result = ExitResult()
