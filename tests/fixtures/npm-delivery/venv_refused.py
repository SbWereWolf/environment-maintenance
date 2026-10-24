#!/usr/bin/env python3
"""A failed venv may leave files; detect any forbidden following pip step."""
from pathlib import Path
import os
import shutil
import sys

module = sys.argv[sys.argv.index('-m') + 1] if '-m' in sys.argv else None
if module != 'venv':
    Path(os.environ['NPM_TEST_PIP_MARKER']).write_text('unexpected following step')
    raise SystemExit(91)
target = Path(sys.argv[-1])
(target / 'bin').mkdir(parents=True, exist_ok=True)
shutil.copyfile(Path(__file__).with_name('pip_must_not_run.sh'), target / 'bin/python')
(target / 'bin/python').chmod(0o700)
print('NPM-TEST-VENV-REFUSED', file=sys.stderr)
raise SystemExit(17)
