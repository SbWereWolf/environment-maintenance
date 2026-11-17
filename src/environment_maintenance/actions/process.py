"""EM supplies a normal Bash command for its cwd/environment policy."""
from copy import deepcopy
from importlib.resources import files
from command_execution import ProcessWorker


def run_command(invocation):
    script = str(files('environment_maintenance').joinpath('resources/commands/invoke.bash'))
    argv = ['bash', script, invocation['cwd'], str(len(invocation['env']))]
    argv.extend(key + '=' + value for key, value in invocation['env'].items())
    argv.extend(invocation['argv'])
    raw = ProcessWorker().run(argv, stdin=invocation.get('stdin'))
    if raw.launch_error:
        raise OSError(raw.launch_error['message'])
    return dict(invocation=deepcopy(invocation), exit_code=raw.returncode,
                stdout=raw.stdout, stderr=raw.stderr)
