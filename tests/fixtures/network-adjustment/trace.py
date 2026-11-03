"""This side effect must never execute during a mixed-selection refusal."""
from pathlib import Path
import sys


Path(sys.argv[1]).write_text('external command executed\n', encoding='utf-8')
