"""Consumer-owned path handling and Unix publication of pure CE JSON."""
from importlib.resources import files
from command_execution import JSONCodec, ProcessWorker


def read_json(path):
    try:
        script = str(files('environment_maintenance').joinpath('resources/commands/read.bash'))
        raw = ProcessWorker().run(['bash', script, str(path)])
        if raw.returncode != 0 or raw.launch_error:
            raise ValueError(raw.stderr.decode('utf-8', 'replace').rstrip() or str(raw.launch_error))
        return JSONCodec('ce-object-v1').loads(raw.stdout.decode('utf-8'))
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise ValueError(f'Cannot read {path}: {error}') from error


def write_json(path, document):
    try:
        payload = (JSONCodec('ce-object-v1').dumps(document, indent=2) + '\n').encode('utf-8')
        script = str(files('environment_maintenance').joinpath('resources/commands/write.bash'))
        raw = ProcessWorker().run(['bash', script, str(path), '0600'], stdin=payload)
        if raw.returncode != 0 or raw.launch_error:
            raise ValueError(raw.stderr.decode('utf-8', 'replace').rstrip() or str(raw.launch_error))
    except (OSError, TypeError, ValueError) as error:
        raise ValueError(f'Cannot write {path}: {error}') from error
