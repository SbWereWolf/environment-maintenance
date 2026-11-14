import sys
sys.stdout.buffer.write(b'package-out\x00\xff')
sys.stderr.buffer.write(b'package-err\xfe')
sys.exit(7)
