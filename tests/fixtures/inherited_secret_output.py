import os
import sys
import time


secret = os.environ["TOKEN"]
stream = sys.stdout if sys.argv[1] == "stdout" else sys.stderr
mode = sys.argv[2]
stream.write(secret[:9] if mode == "timeout" else secret)
stream.flush()
if mode == "timeout":
    time.sleep(1)
