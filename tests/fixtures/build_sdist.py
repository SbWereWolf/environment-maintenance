import json
from setuptools import build_meta
import sys


filename = build_meta.build_sdist(sys.argv[1])
print(json.dumps({"sdist": filename}))
