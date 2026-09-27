import sys
import time


secret = sys.argv[1]
stream = sys.stdout if sys.argv[2] == "stdout" else sys.stderr
mode = sys.argv[3]
stream.write(secret[:9] if mode == "timeout" else secret)
stream.flush()
if mode == "timeout":
    time.sleep(1)
