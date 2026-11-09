"""Transparent CLI fixtures and cleanup restricted to this fixture's own groups."""
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from npm_delivery_support import living_group

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/run-stop"
STARTER = ROOT / "examples/process-launch/start_console.py"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def wait_for(predicate, description):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError("Fixture watchdog: " + description)


def command(label, mode="launch"):
    value = fixture("command.json")
    value["argv"][3:] = [label, mode]
    return value


def application(label, mode="launch", *, identifier=None):
    return {"id": label if identifier is None else identifier, "commands": [command(label, mode)]}


class Lab:
    def __init__(self, directory):
        self.base = Path(directory)
        self.root = self.base / "project with spaces"
        self.root.mkdir(parents=True)
        self.tmp = self.base / "os-temp"
        self.tmp.mkdir()
        self.store = self.tmp / "environment-maintenance"
        self.main = self.root / "start-app.json"
        self.values = self.root / "parameters.json"
        self.events = self.root / "events.jsonl"
        self.children = []
        self.terminal_groups = []
        self.calls = 0
        self.env = dict(os.environ, TMPDIR=str(self.tmp), PYTHONPATH=os.pathsep.join(
            [str(ROOT / "src"), str(FIXTURES)]))
        write(self.main, fixture("main.json"))
        values = fixture("parameters.json")
        values.update(python=sys.executable, probe=str(FIXTURES / "probe.py"),
                      root=str(self.root), tmp=str(self.tmp),
                      display=os.environ.get("DISPLAY", ""), home=str(Path.home()))
        write(self.values, values)
        for op, ids in [("infra", ["alpha", "beta"]), ("deps", ["vendor"]),
                        ("adjust", ["align"]), ("check", ["extra"])]:
            rows = [application(identifier, "marker") for identifier in ids]
            if op in ("infra", "deps"):
                for row in rows:
                    row["checks"] = {"presence": {"commands": [command("presence-" + row["id"], "marker")]}}
            write(self.root / (op + ".json"), {"requirements": rows})
        self.run_rows([application("A"), application("B"), application("C")])

    def run_rows(self, rows):
        write(self.root / "run.json", {"applications": deepcopy(rows),
                                      "owner": {"keep": [False, 0, "metadata"]}})

    def trace(self):
        return [json.loads(line) for line in self.events.read_text().splitlines()] if self.events.exists() else []

    def labels(self):
        return [row["label"] for row in self.trace()]

    def call(self, *arguments, cwd=None, entry=None, deny=None, env=None):
        selected = dict(self.env)
        if env:
            selected.update(env)
        if entry is not None:
            argv = [str(entry), *map(str, arguments)]
        elif deny is not None:
            argv = [sys.executable, "-B", str(FIXTURES / "stop_fault.py"), str(deny), *map(str, arguments)]
        else:
            argv = [sys.executable, "-B", "-m", "environment_maintenance", *map(str, arguments)]
        completed = subprocess.run(argv, cwd=cwd or self.root, env=selected,
                                   capture_output=True, timeout=20)
        self.calls += 1
        prefix = self.base / "captures" / str(self.calls)
        prefix.parent.mkdir(exist_ok=True)
        prefix.with_suffix(".stdout").write_bytes(completed.stdout)
        prefix.with_suffix(".stderr").write_bytes(completed.stderr)
        write(prefix.with_suffix(".json"), {"argv": argv, "cwd": str(cwd or self.root),
                                           "exit_code": completed.returncode})
        return completed

    def answer(self, *arguments, code=0, **options):
        completed = self.call(*arguments, **options)
        assert completed.returncode == code, (completed.stdout, completed.stderr)
        assert completed.stdout.strip(), completed.stderr
        return json.loads(completed.stdout)

    def state_path(self, title):
        return self.store / ("env-" + title + ".json")

    def state(self, title):
        return json.loads(self.state_path(title).read_text())

    def seed(self, title, applications, *, version=1, basename=None):
        record = fixture("state.json")
        record.update({"environment-title": title, "format-version": version,
                       "applications": {key: {"pgid": group} for key, group in applications.items()}})
        write(self.state_path(title if basename is None else basename), record)

    def spawn(self, label, mode="launch"):
        completed = subprocess.run([sys.executable, "-B", str(FIXTURES / "probe.py"),
                                    str(self.root), label, mode], env=self.env,
                                   capture_output=True, timeout=10)
        assert completed.returncode == 0, completed.stderr
        return json.loads(completed.stdout)["pgid"]

    def started(self, label):
        path = self.root / (label + ".started.json")
        return wait_for(lambda: json.loads(path.read_text()) if path.exists() else None, label + " started")

    def dead(self, group):
        wait_for(lambda: not living_group(group), "owned group stopped")

    def terminal_row(self, label):
        row = application(label)
        row["commands"][0]["argv"] = [
            "${python}", "-B", str(STARTER), "--stdout-log", str(self.root / (label + ".out")),
            "--stderr-log", str(self.root / (label + ".err")), "--",
            "/usr/bin/zutty", "-font", "DejaVuSansMono", "-fontpath",
            "/usr/share/fonts/truetype/dejavu", "-title", "EM-RUN-STOP-" + label,
            "-e", "${python}", "-B", str(FIXTURES / "worker.py"), "${root}", label]
        return row

    def close(self):
        if self.store.exists():
            self.store.chmod(0o700)
            for path in self.store.iterdir():
                path.chmod(0o600)
        groups = set(self.terminal_groups)
        for path in self.root.glob("*.started.json"):
            row = json.loads(path.read_text())
            assert row["root"] == str(self.root)
            groups.add(row["pgid"])
        # Terminal workers can have their own PTY group. IDs come only from own
        # handshakes or starter Popen, never a system-wide process name.
        for group in groups:
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for group in groups:
            deadline = time.monotonic() + 3
            while living_group(group) and time.monotonic() < deadline:
                time.sleep(.02)
            if living_group(group):
                os.killpg(group, signal.SIGKILL)
                self.dead(group)
        for process in self.children:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
        write(self.base / "resource-closure.json",
              {"groups": sorted(groups), "all_owned_groups_stopped": all(not living_group(g) for g in groups)})
