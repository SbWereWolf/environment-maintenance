"""Run one declared action with bounded capture and an exact result protocol."""

import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def _protocol(raw, requirement_id, role, schema):
    value = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_nonfinite)
    if not isinstance(value, dict):
        raise ValueError("Action result must be a JSON object")
    base = {"schema", "requirement_id", "action"}
    if value.get("schema") != schema or value.get("requirement_id") != requirement_id or value.get("action") != role:
        raise ValueError("Action result identity does not match invocation")
    if role == "check":
        state = value.get("state")
        if type(state) is not str or state not in {"satisfied", "missing", "invalid", "unavailable"}:
            raise ValueError("Invalid check state")
        required = base | {"state"}
        if state == "unavailable":
            required |= {"cause", "recommendations"}
            if not isinstance(value.get("cause"), str) or not value["cause"].strip():
                raise ValueError("Unavailable cause is required")
            advice = value.get("recommendations")
            if not isinstance(advice, list) or not advice or any(
                not isinstance(item, str) or not item.strip() for item in advice
            ):
                raise ValueError("Unavailable recommendations are required")
    else:
        required = base | {"outcome"}
        if value.get("outcome") != "completed" or type(value.get("outcome")) is not str:
            raise ValueError("Invalid mutation outcome")
    if set(value) != required:
        raise ValueError("Action result fields do not match the declared protocol")
    return value


def _kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _capture(process, limit, bound):
    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    selector = selectors.DefaultSelector()
    for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
        os.set_blocking(pipe.fileno(), False)
        selector.register(pipe, selectors.EVENT_READ, name)
    deadline = time.monotonic() + bound
    cleanup_deadline = None
    timed_out = False
    truncated = False
    while selector.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0 and cleanup_deadline is None:
            timed_out = True
            _kill_group(process)
            cleanup_deadline = time.monotonic() + 1
        if cleanup_deadline is not None and time.monotonic() >= cleanup_deadline:
            break
        ready = selector.select(0.05 if cleanup_deadline is not None else min(remaining, 0.05))
        for key, _ in ready:
            chunk = os.read(key.fileobj.fileno(), 65536)
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            bucket = outputs[key.data]
            room = max(0, limit - len(bucket))
            bucket.extend(chunk[:room])
            if len(chunk) > room:
                if not truncated:
                    truncated = True
                    _kill_group(process)
                    cleanup_deadline = time.monotonic() + 1
    selector.close()
    if timed_out or truncated:
        _kill_group(process)
    try:
        process.wait(timeout=max(0.01, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(process)
        process.wait()
    return bytes(outputs["stdout"]), bytes(outputs["stderr"]), timed_out, not truncated


def run_action(action, requirement_id, role, *, cwd, environ):
    base = Path(cwd)
    directory = Path(action["cwd"])
    if not directory.is_absolute():
        directory = base / directory
    environment = dict(environ)
    environment.update(action["env"])
    invocation = {"argv": list(action["argv"]), "cwd": str(directory), "env": environment}
    response = {
        "status": "protocol_failure",
        "invocation": invocation,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "capture_complete": True,
        "timed_out": False,
        "error": "Action did not produce a valid result",
    }
    try:
        directory = directory.resolve()
    except (OSError, RuntimeError) as exc:
        response["error"] = f"Cannot resolve action cwd: {exc}"
        return response
    invocation["cwd"] = str(directory)
    try:
        process = subprocess.Popen(
            action["argv"],
            cwd=directory,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        response["error"] = f"Cannot launch action: {exc}"
        return response
    stdout, stderr, timed_out, complete = _capture(
        process, action["max_output_bytes"], action["execution_bound_seconds"]
    )
    response.update(
        exit_code=process.returncode,
        stdout=stdout.decode("utf-8", "ignore"),
        stderr=stderr.decode("utf-8", "ignore"),
        capture_complete=complete,
        timed_out=timed_out,
    )
    if timed_out:
        response["error"] = "Action exceeded execution_bound_seconds"
    elif not complete:
        response["error"] = "Action exceeded max_output_bytes"
    elif process.returncode != 0:
        response["error"] = f"Action exited with status {process.returncode}"
    else:
        try:
            decoded = stdout.decode("utf-8")
            stderr.decode("utf-8")
            parsed = _protocol(decoded, requirement_id, role, action["output"]["schema"])
        except (UnicodeError, ValueError) as exc:
            response["error"] = f"Invalid action output: {exc}"
        else:
            response["status"] = "passed"
            response["response"] = parsed
            response["error"] = None
    return response
