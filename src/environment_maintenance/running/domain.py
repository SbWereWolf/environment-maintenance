"""Names and submitted-group replies, without OS health or PID discovery."""
import json


def validate_environment_title(title):
    if not title or title == 'all' or any(
        not (char.isalnum() or char in '-_.' or
             (ord(char) > 127 and char.isprintable() and not char.isspace())) for char in title
    ):
        raise ValueError('Environment name must be nonempty, shell-safe and different from all')
    return title


def submitted_pgid(result, declared_command_count):
    if len(result['commands']) != declared_command_count:
        return None
    try:
        value = json.loads(result['commands'][-1]['stdout'])
    except (ValueError, UnicodeError):
        return None
    if (isinstance(value, dict) and value.get('status') == 'submitted'
            and type(value.get('pgid')) is int and value['pgid'] > 0):
        return value['pgid']
    return None
