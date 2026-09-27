import subprocess
import sys
import time

subprocess.Popen([
    sys.executable,
    "-S",
    sys.argv[1],
    sys.argv[2],
    sys.argv[3],
])
time.sleep(60)
