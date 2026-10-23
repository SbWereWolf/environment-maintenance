"""Submit an explicit external command without owning its terminal's lifetime."""
import argparse
import json
import subprocess
import sys


def _submit_command(command, stdout_log, stderr_log):
    with open(stdout_log, 'ab') as stdout, open(stderr_log, 'ab') as stderr:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, start_new_session=True)
        return process.pid


def main(argv=None):
    parser = argparse.ArgumentParser(description='Передать запуск выбранной команды консоли')
    parser.add_argument('--stdout-log', required=True, help='Файл полного stdout команды')
    parser.add_argument('--stderr-log', required=True, help='Файл полного stderr команды')
    parser.add_argument('command', nargs=argparse.REMAINDER, help='COMMAND и аргументы после --')
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('command is required after --')
    if args.stdout_log == args.stderr_log:
        parser.error('--stdout-log and --stderr-log require different paths: ' + args.stdout_log)
    try:
        pid = _submit_command(command, args.stdout_log, args.stderr_log)
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(dict(status='submitted', pid=pid), separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
