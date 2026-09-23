"""Shared bounded subprocess execution, not a command-policy or prerequisite owner."""
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def run(action, *, cwd, environ, request=None):
    start=time.monotonic(); timed_out=False; error=None; code=None
    limit=action.get('max_output_bytes',262144)
    env=dict(environ);env.update(action.get('env',{}))
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as inp:
        if request is not None:inp.write(request.encode('utf-8'))
        inp.seek(0)
        try:
            proc=subprocess.Popen(action['argv'],cwd=action.get('cwd',str(cwd)),env=env,
                                  stdin=inp,stdout=out,stderr=err,start_new_session=True)
            try:code=proc.wait(timeout=action['timeout'])
            except subprocess.TimeoutExpired:
                timed_out=True
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                code=proc.wait()
        except (OSError,ValueError) as exc:error=str(exc)
        out.seek(0);err.seek(0)
        stdout=out.read(limit+1);stderr=err.read(limit+1)
    truncated=len(stdout)>limit or len(stderr)>limit
    return {'status':'passed' if code==0 and not timed_out and not truncated and not error else 'failed',
            'exit_code':code,'timed_out':timed_out,'capture_complete':not truncated,
            'stdout':stdout[:limit].decode('utf-8','replace'),'stderr':stderr[:limit].decode('utf-8','replace'),
            'error':error,'duration_seconds':round(time.monotonic()-start,4)}
