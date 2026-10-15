"""Invoke the declared standard backend; capture is owned by the caller."""
import sys
from setuptools.build_meta import build_wheel

build_wheel(sys.argv[1])
