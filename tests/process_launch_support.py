"""Transparent Linux X11 driver addressing only this experiment's own windows."""
import ctypes
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import select
import subprocess
import time


class KeyEvent(ctypes.Structure):
    _fields_ = [('type', ctypes.c_int), ('serial', ctypes.c_ulong), ('send_event', ctypes.c_int),
        ('display', ctypes.c_void_p), ('window', ctypes.c_ulong), ('root', ctypes.c_ulong),
        ('subwindow', ctypes.c_ulong), ('time', ctypes.c_ulong), ('x', ctypes.c_int),
        ('y', ctypes.c_int), ('x_root', ctypes.c_int), ('y_root', ctypes.c_int),
        ('state', ctypes.c_uint), ('keycode', ctypes.c_uint), ('same_screen', ctypes.c_int)]


class Event(ctypes.Union):
    _fields_ = [('key', KeyEvent), ('padding', ctypes.c_long * 24)]


def wait_for(predicate, description, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.03)
    raise AssertionError('Did not observe ' + description)


class ConsoleLab:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.observations = []
        self.children = []
        self.owned = {}

    def record(self, kind, **values):
        row = dict(kind=kind, **values)
        self.observations.append(row)
        with (self.directory / 'observations.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row) + '\n')

    def ready(self, label):
        path = self.directory / (label + '.ready.json')
        row = wait_for(lambda: json.loads(path.read_text()) if path.exists() else None,
                       label + ' worker handshake')
        assert row['label'] == label and row['tty'].startswith('/dev/pts/')
        assert type(row['pid']) is int and row['pid'] > 0
        self.owned[label] = row
        self.record('ready', **row)
        return row

    def visible(self, label):
        row = self.owned[label]
        window = str(row['window'])
        result = subprocess.run(['/usr/bin/xwininfo', '-id', window], capture_output=True, timeout=3)
        self.record('window', label=label, exit_code=result.returncode,
                    stdout=result.stdout.decode(), stderr=result.stderr.decode())
        assert result.returncode == 0 and b'IsViewable' in result.stdout
        return int(window, 0)

    def connection(self, display_name=None):
        x = ctypes.CDLL('libX11.so.6')
        signatures = {
            'XOpenDisplay': ([ctypes.c_char_p], ctypes.c_void_p),
            'XCloseDisplay': ([ctypes.c_void_p], ctypes.c_int),
            'XMoveWindow': ([ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int], ctypes.c_int),
            'XSync': ([ctypes.c_void_p, ctypes.c_int], ctypes.c_int),
            'XStringToKeysym': ([ctypes.c_char_p], ctypes.c_ulong),
            'XKeysymToKeycode': ([ctypes.c_void_p, ctypes.c_ulong], ctypes.c_ubyte),
            'XDefaultRootWindow': ([ctypes.c_void_p], ctypes.c_ulong),
            'XSendEvent': ([ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long,
                            ctypes.POINTER(Event)], ctypes.c_int),
        }
        for name, (arguments, result) in signatures.items():
            getattr(x, name).argtypes, getattr(x, name).restype = arguments, result
        display = x.XOpenDisplay(None if display_name is None else display_name.encode())
        assert display, 'Linux X11 display prerequisite unavailable'
        return x, display

    def input(self, label, keys, *, control=False):
        window = self.visible(label)
        x, display = self.connection()
        try:
            x.XMoveWindow(display, window, 20 + list(self.owned).index(label) * 830, 20)
            x.XSync(display, 0)
            # Address the observed owned window directly. Global focus can change
            # independently under WSLg and must not redirect test input elsewhere.
            def event(key, pressed):
                symbol = x.XStringToKeysym(key.encode('ascii'))
                code = x.XKeysymToKeycode(display, symbol)
                assert code > 0
                event = Event()
                event.key = KeyEvent(type=2 if pressed else 3, display=display,
                    window=window, root=x.XDefaultRootWindow(display), x=10, y=10,
                    state=4 if control else 0, keycode=code, same_screen=1)
                assert x.XSendEvent(display, window, 0, 1 if pressed else 2, ctypes.byref(event))
                x.XSync(display, 0)
                time.sleep(0.02)
            for key in keys:
                event(key, 1)
                # Ctrl+C may destroy the terminal immediately. Synthetic events do
                # not hold global key state, so no release to a dead window is needed.
                if not control:
                    event(key, 0)
            x.XSync(display, 0)
            self.record('input', label=label, window=window, keys=keys, control=control)
        finally:
            x.XCloseDisplay(display)

    def reply(self, label, text):
        self.input(label, [*text, 'Return'])
        path = self.directory / (label + '.reply.json')
        def current_reply():
            value = json.loads(path.read_text()) if path.exists() else None
            return value if value and value.get('text') == text else None
        row = wait_for(current_reply, label + ' response to actual console input')
        assert row == dict(label=label, text=text, pid=self.owned[label]['pid'])
        self.record('reply', **row)

    def stop(self, label):
        self.input(label, ['c'], control=True)
        path = self.directory / (label + '.stopped.json')
        row = wait_for(lambda: json.loads(path.read_text()) if path.exists() else None,
                       label + ' console Ctrl+C stop')
        assert row == dict(label=label, signal=2, pid=self.owned[label]['pid'])
        self.record('stopped', **row)

    def screenshot(self, label):
        window = self.visible(label)
        x, display = self.connection()
        try:
            # Arrange every observed owned console before the first capture.
            # A still-overlapping neighbour can occlude an otherwise viewable
            # GL-backed window and produce a blank capture of its contents.
            for index, owned_label in enumerate(self.owned):
                owned_window = self.visible(owned_label)
                position = (20 + index * 830, 20)
                x.XMoveWindow(display, owned_window, *position)
                self.record('arrangement', label=owned_label, window=owned_window,
                            x=position[0], y=position[1])
            x.XSync(display, 0)
            time.sleep(0.15)
            path = self.directory / (label + '.png')
            result = subprocess.run(['/usr/bin/import', '-window', hex(window), str(path)],
                                    capture_output=True, timeout=5)
            self.record('screenshot', label=label, path=str(path), exit_code=result.returncode,
                        stderr=result.stderr.decode())
            assert result.returncode == 0 and path.is_file()
            spread = subprocess.run(['/usr/bin/identify', '-format', '%[fx:standard_deviation]',
                str(path)], capture_output=True, timeout=5)
            assert spread.returncode == 0 and float(spread.stdout) > 0.001, 'Console image is blank'
        finally:
            x.XCloseDisplay(display)

    def close(self):
        # Exact worker handshake files establish ownership even if an assertion failed.
        for path in self.directory.glob('*.ready.json'):
            row = json.loads(path.read_text())
            try:
                os.kill(row['pid'], signal.SIGINT)
            except ProcessLookupError:
                pass
        for child in self.children:
            try:
                child.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                child.terminate()
                child.communicate(timeout=4)


def terminal_argv(python, worker, directory, label):
    return ['/usr/bin/zutty', '-font', 'DejaVuSansMono', '-fontpath',
            '/usr/share/fonts/truetype/dejavu', '-title', 'ENV2-007-' + label,
            '-e', python, '-B', str(worker), str(directory), label]


@contextmanager
def visible_server(directory, executable, libraries):
    """Own a VISIBLE Xephyr with a private Latin map, never alter the host map."""
    directory = Path(directory)
    host = os.environ['DISPLAY']
    read_fd, write_fd = os.pipe()
    title = 'ENV2-007-visible-' + str(os.getpid())
    argv = [str(executable), '-displayfd', str(write_fd), '-screen', '1700x650',
        '-xkb-layout', 'us', '-no-host-grab', '-nolisten', 'local', '-nolisten', 'unix',
        '-listen', 'tcp', '-extension', 'MIT-SHM',
        '-noreset', '-title', title]
    process = subprocess.Popen(argv, env=dict(os.environ, LD_LIBRARY_PATH=str(libraries)),
        pass_fds=(write_fd,), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.close(write_fd)
    nested = None
    try:
        assert select.select([read_fd], [], [], 10)[0], 'Visible Xephyr did not publish a display'
        number = os.read(read_fd, 64).decode().strip()
        assert number.isdigit() and process.poll() is None, 'Visible Xephyr startup failed'
        nested = '127.0.0.1:' + number
        # Xephyr owns this map. WSLg user layout changes must not enter the test server.
        configured = subprocess.run(['/usr/bin/setxkbmap', '-display', nested, 'us'],
            capture_output=True, timeout=5)
        assert configured.returncode == 0, configured.stderr
        os.environ['DISPLAY'] = nested
        def capture():
            tree = subprocess.run(['/usr/bin/xwininfo', '-root', '-tree'],
                env=dict(os.environ, DISPLAY=host), capture_output=True, timeout=3)
            import re
            (directory / 'visible-host-tree.txt').write_bytes(tree.stdout)
            candidates = [line for line in tree.stdout.splitlines() if title.encode() in line]
            assert tree.returncode == 0 and len(candidates) == 1, candidates
            window = re.search(rb'(0x[0-9a-fA-F]+)', candidates[0]).group(1).decode()
            observed = subprocess.run(['/usr/bin/xwininfo', '-id', window],
                env=dict(os.environ, DISPLAY=host), capture_output=True, timeout=3)
            assert observed.returncode == 0 and b'IsViewable' in observed.stdout
            x, display = ConsoleLab(directory).connection(host)
            try:
                x.XMoveWindow(display, int(window, 16), 20, 20)
                x.XSync(display, 0)
                time.sleep(0.15)
                screenshot = subprocess.run(['/usr/bin/import', '-window', window,
                    str(directory / 'visible-host-server.png')], env=dict(os.environ, DISPLAY=host),
                    capture_output=True, timeout=5)
                assert screenshot.returncode == 0, screenshot.stderr
                spread = subprocess.run(['/usr/bin/identify', '-format', '%[fx:standard_deviation]',
                    str(directory / 'visible-host-server.png')], capture_output=True, timeout=5)
                assert spread.returncode == 0 and float(spread.stdout) > 0.001, 'Visible server image is blank'
                (directory / 'visible-host-server.xwininfo').write_bytes(observed.stdout)
            finally:
                x.XCloseDisplay(display)
        yield capture
    finally:
        os.close(read_fd)
        os.environ['DISPLAY'] = host
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        (directory / 'visible-server.stdout').write_bytes(stdout)
        (directory / 'visible-server.stderr').write_bytes(stderr)
        (directory / 'visible-server.json').write_text(json.dumps(dict(argv=argv,
            host_display=host, own_display=nested, pid=process.pid,
            exit_code=process.returncode, host_keyboard_writes=False)), encoding='utf-8')
