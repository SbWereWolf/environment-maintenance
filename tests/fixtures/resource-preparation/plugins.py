"""Test-owned external implementations; no product imports or production oracle."""
import math


class ExitResult:
    def interpret(self, raw, options):
        success = raw['exit_code'] in options['accept']
        return dict(success=success, value=dict(tag=options['tag'], code=raw['exit_code']),
                    error=None if success else 'exit not accepted')


class ByteResult:
    def interpret(self, raw, options):
        success = raw['stdout'].startswith(b'\xff\x00ready\r\n')
        return dict(success=success, value=['bytes', False, 0],
                    error=None if success else 'bytes not accepted', selected='bytes')


class Answer:
    def __init__(self, value):
        self.value = value

    def interpret(self, raw, options):
        return dict(success=True, value=self.value, error=None)


class Throwing:
    def interpret(self, raw, options):
        raise ValueError('external interpreter refused')


class Malformed:
    def interpret(self, raw, options):
        return dict(success='yes', value=0, error=None)


exit_result = ExitResult()
byte_result = ByteResult()
throwing = Throwing()
malformed = Malformed()
opaque = Answer(b'opaque\x00\xff')
integer_key = Answer({1: 'integer-key'})
tuple_value = Answer(('tuple', 0))
not_a_number = Answer(math.nan)
infinity = Answer(math.inf)
not_interpreter = object()
