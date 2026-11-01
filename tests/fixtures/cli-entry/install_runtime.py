"""Fixture-owned tool invoked by declared SDK preparation commands."""
from pathlib import Path
import shutil
import subprocess
import sys

entry, runtime, plugin, probe, target = map(Path, sys.argv[1:])
target.mkdir()
shutil.copytree(runtime, target / '.venv')
shutil.copy2(entry, target / 'start-app')
(target / 'tools').mkdir()
shutil.copy2(probe, target / 'tools' / 'probe.py')
python = target / '.venv' / 'bin' / 'python'
site = subprocess.check_output(
    [str(python), '-I', '-B', '-c', 'import site; print(site.getsitepackages()[0])'],
    text=True,
).strip()
shutil.copy2(plugin, Path(site) / 'env2_cli_plugins.py')
