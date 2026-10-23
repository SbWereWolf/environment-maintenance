"""Independent interpreters receive raw bytes; no execution or configuration ownership."""
class Exit:
    def interpret(self, result, options):
        success = result['exit_code'] in options['accept']
        return dict(success=success, value=result['exit_code'],
                    error=None if success else 'selected exit rejected')


class Opaque:
    def interpret(self, result, options):
        return dict(success=True, value=result['stdout'], error=None)


class Broken:
    def interpret(self, result, options):
        raise ValueError('selected interpreter refused launch result')


exit_result = Exit()
opaque_result = Opaque()
broken_result = Broken()
